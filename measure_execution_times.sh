#!/bin/bash

# Measure execution times for Stage4 output configs
# Runs each config 3 times via curl and records timing
#
# OUT OF ORDER since 2026-09-05. It drove /api/schema/pipeline/stage3-4, which
# has been removed, and it reads `stage3_time_ms` / `stage4_time_ms` out of
# that route's answer -- fields no route on this platform returns now. Its
# payload also still carries `execution_mode`, which the backend no longer reads. Run as
# it stands it would post to a dead address, take the failure branch on every
# config and write a timing file of zeros, which
# update_chunks_with_timing.py would then stamp into the chunk definitions as
# measured durations.
#
# It stops here rather than measuring something else: the timing model this
# parses -- Stage 3 once, Stage 4 three times, both read off one answer -- has
# no counterpart in the routes that replaced it, so pointing it at one of them
# would be a new harness rather than this one repaired.
echo "measure_execution_times.sh drives /api/schema/pipeline/stage3-4, which no" >&2
echo "longer exists. It would write a timing file of zeros. Not run." >&2
exit 1

# Test prompt
TEST_PROMPT='Massive stone manor centered, light-colored ashlar facade, frontal orientation, rusticated ground floor, regularly spaced fenestration above, pitched roof apex. Lateral light from upper left models wall depth through graduated shadow. Foreground: cultivated fields in ochre-green, hedge rows receding linearly, middle-ground figures—man with scythe left, two women field-working center, child at entrance. Cattle and sheep distributed right. Distant hills transition blue-gray, sky gradates pale horizon to deeper tone zenith. Oil paint medium: architecture rendered precise linear construction with thin stone-surface glazes; landscape built additive pigment layers, warm-cool tonal modulation creating spatial recession. Light from upper left creates warm wall reflections, cool shadow accumulation in field depressions. Ground plane slopes gently downward from house foundation. Atmospheric perspective compresses background features. Hedge geometry creates orthogonal depth vectors. Human figures maintain natural posture alignment within compositional grid. Animal forms occupy lower right quadrant, static positioning. Sky occupies upper third, graduated luminosity. All forms receive volumetric modeling through shadow-highlight distribution. Surface texture differentiation: smooth stone versus vegetation texture variation. Spatial layering: house plane, middle-ground activity zone, distant landform recession. Light quality: warm diffuse illumination with sharp shadow edges indicating clear atmospheric conditions. No symbolic content, no narrative implication—purely spatial, material, and perceptual configuration as observable physical arrangement.'

# Server configuration
API_URL="http://localhost:17802/api/schema/pipeline/stage3-4"

# Config list
declare -a CONFIGS=(
    "sd35_large"
    "gpt_image_1"
    "gemini_3_pro_image"
    "qwen"
    "ltx_video"
    "wan22_video"
    "acenet_t2instrumental"
    "stableaudio_open"
)

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Results files
RESULTS_FILE="timing_results.json"
STAGE3_FILE="stage3_timing.json"
echo "{}" > "$RESULTS_FILE"

echo "======================================================================"
echo "Stage3 + Stage4 Execution Time Measurement Script"
echo "======================================================================"
echo ""
echo "Test prompt length: ${#TEST_PROMPT} characters"
echo "Number of configs to test: ${#CONFIGS[@]}"
echo "Runs per config: 3"
echo ""
echo "Stage 3 will be measured once (same for all configs)"
echo "Stage 4 will be measured 3x per config"
echo ""
echo "Results will be saved to:"
echo "  - Stage 3: $STAGE3_FILE"
echo "  - Stage 4: $RESULTS_FILE"
echo ""
read -p "Press Enter to start measurements..."

# Function to measure a single run and extract timings
measure_run() {
    local config_id=$1
    local run_num=$2

    echo -ne "  Run $run_num/3... " >&2

    # Create JSON payload
    local payload=$(jq -n \
        --arg stage2 "$TEST_PROMPT" \
        --arg config "$config_id" \
        '{
            stage2_result: $stage2,
            output_config: $config,
            execution_mode: "eco",
            safety_level: "open"
        }')

    # Measure total execution time and make request
    local start_time=$(date +%s.%N)

    # Use separate temp files for response and status
    local tmp_body=$(mktemp)
    local tmp_status=$(mktemp)

    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        -w "%{http_code}" \
        -o "$tmp_body" \
        > "$tmp_status"

    local end_time=$(date +%s.%N)

    local status_code=$(cat "$tmp_status")
    local body=$(cat "$tmp_body")

    # Clean up temp files
    rm -f "$tmp_body" "$tmp_status"

    # Calculate total execution time (force English locale for decimal point)
    local total_time=$(LC_NUMERIC=C printf "%.2f" $(echo "$end_time - $start_time" | bc))

    if [ "$status_code" == "200" ]; then
        # Extract stage3 and stage4 times from response
        local stage3_ms=$(echo "$body" | jq -r '.stage3_time_ms // 0')
        local stage4_ms=$(echo "$body" | jq -r '.stage4_time_ms // 0')

        # Validate extracted values
        if [ -z "$stage3_ms" ] || [ "$stage3_ms" == "null" ]; then
            stage3_ms=0
        fi
        if [ -z "$stage4_ms" ] || [ "$stage4_ms" == "null" ]; then
            stage4_ms=0
        fi

        # Convert to seconds (force English locale for decimal point)
        local stage3_time=$(LC_NUMERIC=C printf "%.2f" $(echo "scale=2; $stage3_ms / 1000" | bc))
        local stage4_time=$(LC_NUMERIC=C printf "%.2f" $(echo "scale=2; $stage4_ms / 1000" | bc))

        echo -e "${GREEN}✓${NC} Total: ${total_time}s (Stage3: ${stage3_time}s, Stage4: ${stage4_time}s)" >&2

        # Return both times separated by |
        echo "${stage3_time}|${stage4_time}"
        return 0
    else
        echo -e "${RED}✗${NC} Failed with status $status_code" >&2
        echo "0|0"
        return 1
    fi
}

# Arrays to store Stage 3 times
stage3_times=()

# Process each config
for config_id in "${CONFIGS[@]}"; do
    echo ""
    echo "======================================================================"
    echo -e "${BLUE}Testing config: $config_id${NC}"
    echo "======================================================================"

    stage4_times=()

    # Run 3 times
    for run in 1 2 3; do
        result=$(measure_run "$config_id" "$run")
        if [ $? -eq 0 ]; then
            # Split result into stage3 and stage4 times
            IFS='|' read -r stage3_time stage4_time <<< "$result"
            stage3_times+=("$stage3_time")
            stage4_times+=("$stage4_time")
        fi

        # Small delay between runs
        if [ $run -lt 3 ]; then
            sleep 2
        fi
    done

    # Calculate Stage 4 results if we have 3 successful runs
    if [ ${#stage4_times[@]} -eq 3 ]; then
        firstrun="${stage4_times[0]}"
        run2="${stage4_times[1]}"
        run3="${stage4_times[2]}"

        # Calculate average of runs 2-3 (force English locale)
        average=$(LC_NUMERIC=C printf "%.2f" $(echo "scale=2; ($run2 + $run3) / 2" | bc))

        # Round values
        firstrun=$(LC_NUMERIC=C printf "%.2f" "$firstrun")
        average=$(LC_NUMERIC=C printf "%.2f" "$average")

        echo ""
        echo "──────────────────────────────────────────────────────────────────"
        echo -e "${GREEN}Stage 4 Results for $config_id:${NC}"
        echo "  First run (cold start):  ${firstrun}s"
        echo "  Run 2:                   ${run2}s"
        echo "  Run 3:                   ${run3}s"
        echo "  Average warm time:       ${average}s"
        echo "──────────────────────────────────────────────────────────────────"

        # Save to results file
        jq --arg config "$config_id" \
           --arg firstrun "$firstrun" \
           --arg average "$average" \
           '.[$config] = {execution_time_firstrun: ($firstrun | tonumber), execution_time_average: ($average | tonumber)}' \
           "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
    else
        echo -e "${RED}Failed to complete all 3 runs for $config_id${NC}"
    fi

    # Wait before next config
    echo ""
    echo "Waiting 5 seconds before next config..."
    sleep 5
done

# Calculate Stage 3 average from all runs
if [ ${#stage3_times[@]} -gt 0 ]; then
    echo ""
    echo "======================================================================"
    echo -e "${BLUE}Calculating Stage 3 average from all runs${NC}"
    echo "======================================================================"

    # Get first run (cold start)
    stage3_firstrun="${stage3_times[0]}"

    # Calculate average of all remaining runs (warm runs)
    sum=0
    count=0
    for i in "${!stage3_times[@]}"; do
        if [ $i -gt 0 ]; then
            sum=$(echo "$sum + ${stage3_times[$i]}" | bc)
            count=$((count + 1))
        fi
    done

    if [ $count -gt 0 ]; then
        stage3_average=$(LC_NUMERIC=C printf "%.2f" $(echo "scale=2; $sum / $count" | bc))
    else
        stage3_average="$stage3_firstrun"
    fi

    # Round values
    stage3_firstrun=$(LC_NUMERIC=C printf "%.2f" "$stage3_firstrun")
    stage3_average=$(LC_NUMERIC=C printf "%.2f" "$stage3_average")

    echo ""
    echo "Stage 3 timing (averaged across all configs):"
    echo "  First run (cold start):  ${stage3_firstrun}s"
    echo "  Average warm time:       ${stage3_average}s"

    # Save Stage 3 results
    jq -n \
       --arg firstrun "$stage3_firstrun" \
       --arg average "$stage3_average" \
       '{execution_time_firstrun: ($firstrun | tonumber), execution_time_average: ($average | tonumber)}' \
       > "$STAGE3_FILE"

    echo ""
    echo -e "${GREEN}✓${NC} Stage 3 timing saved to $STAGE3_FILE"
fi

# Print final summary
echo ""
echo "======================================================================"
echo -e "${GREEN}MEASUREMENT COMPLETE${NC}"
echo "======================================================================"
echo ""
echo "Stage 3 results:"
cat "$STAGE3_FILE" | jq '.'
echo ""
echo "Stage 4 results:"
cat "$RESULTS_FILE" | jq '.'

echo ""
echo "======================================================================"
echo "To update chunks with these values, run:"
echo "  python3 update_chunks_with_timing.py"
echo "======================================================================"
