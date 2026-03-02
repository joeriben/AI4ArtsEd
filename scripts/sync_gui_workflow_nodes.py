#!/usr/bin/env python3
"""
Script to sync "über" and "info" (renamed from "about") nodes from API workflows to GUI workflows
"""
import json
from pathlib import Path

# Define the text content for each workflow (same as in add_about_nodes.py)
workflow_texts = {
    # ACROSS
    "ai4artsed_ACROSS_ImageAndSound_2506270842.json": {
        "über": "Bild und Klang\nErzeugt gleichzeitig Bild und Audio aus einem Prompt\nDieser Workflow generiert sowohl ein Bild als auch eine passende Audiodatei aus einem einzigen Prompt für multimediale Kunstprojekte.",
        "info": "Image and Sound\nGenerates both image and audio from a single prompt\nThis workflow creates both an image and matching audio file from one prompt for multimedia art projects."
    },
    "ai4artsed_ACROSS_ImageToSound_2506270842.json": {
        "über": "Bild zu Klang\nWandelt Bildbeschreibungen in Klanglandschaften um\nTransformiert visuelle Prompts in akustische Interpretationen. Der Workflow analysiert die Elemente einer Bildbeschreibung und erzeugt daraus Soundscapes oder Musik.",
        "info": "Image to Sound\nConverts image descriptions into soundscapes\nTransforms visual prompts into acoustic interpretations. The workflow analyzes elements of an image description and creates soundscapes or music."
    },
    
    # AESTHETICS
    "ai4artsed_AESTHETICS_ClichéFilter_V1_2506160013.json": {
        "über": "Klischee-Filter V1\nErkennt klischeehafte Bildmotive und verfolgt verschiedene Strategien, Klischees zu vermeiden\nV1: Direkte Inversion von Klischees. V2: Kontextuelle Neuinterpretation. V3: Kombination beider Ansätze mit verstärktem Negativprompt für maximale Klischee-Vermeidung.",
        "info": "Cliché Filter V1\nDetects clichéd image motifs and pursues different strategies to avoid clichés\nV1: Direct inversion of clichés. V2: Contextual reinterpretation. V3: Combination of both approaches with enhanced negative prompt for maximum cliché avoidance."
    },
    "ai4artsed_AESTHETICS_ClichéFilter_V2_2506211602.json": {
        "über": "Klischee-Filter V2\nErkennt klischeehafte Bildmotive und verfolgt verschiedene Strategien, Klischees zu vermeiden\nV1: Direkte Inversion von Klischees. V2: Kontextuelle Neuinterpretation. V3: Kombination beider Ansätze mit verstärktem Negativprompt für maximale Klischee-Vermeidung.",
        "info": "Cliché Filter V2\nDetects clichéd image motifs and pursues different strategies to avoid clichés\nV1: Direct inversion of clichés. V2: Contextual reinterpretation. V3: Combination of both approaches with enhanced negative prompt for maximum cliché avoidance."
    },
    "ai4artsed_AESTHETICS_ClichéFilter_V3_original_plus_negative_prompt_250616192.json": {
        "über": "Klischee-Filter V3\nErkennt klischeehafte Bildmotive und verfolgt verschiedene Strategien, Klischees zu vermeiden\nV1: Direkte Inversion von Klischees. V2: Kontextuelle Neuinterpretation. V3: Kombination beider Ansätze mit verstärktem Negativprompt für maximale Klischee-Vermeidung.",
        "info": "Cliché Filter V3\nDetects clichéd image motifs and pursues different strategies to avoid clichés\nV1: Direct inversion of clichés. V2: Contextual reinterpretation. V3: Combination of both approaches with enhanced negative prompt for maximum cliché avoidance."
    },
    "ai4artsed_AESTHETICS_HunkyDoryHarmonizer_2507100933.json": {
        "über": "Harmonisierer\nNebenprodukt einer frühen Version des \"Kids-Safety\"-Filters\nVerniedlicht, versüßlicht, harmonisiert. Erzeugt bewusst übertrieben harmonische Bildkompositionen.",
        "info": "Harmonizer\nByproduct of an early version of the \"Kids-Safety\" filter\nCutifies, sweetens, harmonizes. Creates deliberately exaggerated harmonic image compositions."
    },
    
    # ARTS
    "ai4artsed_ARTS_Dada_2506220140.json": {
        "über": "Dadaismus Transformation\nVersetzt sich in die Zeit und Situation dadaistischer Künstler_innen\nNutzt Absurdität, Zufall und Anti-Kunst-Prinzipien zur Transformation alltäglicher Prompts.",
        "info": "Dadaism Transformation\nPlaces itself in the time and situation of Dadaist artists\nUses absurdity, chance and anti-art principles to transform everyday prompts."
    },
    "ai4artsed_ARTS_RandomArtisticStyleApplication_2506121429.json": {
        "über": "Zufälliger Kunststil\nWählt jeweils eine aus 50 globalen Kunst- und kulturellen Ausdrucksformen als Vorlage\nEin experimenteller Workflow zur stilistischen Interpretation von Prompts.",
        "info": "Random Artistic Style\nSelects one of 50 global art and cultural forms of expression as template\nAn experimental workflow for stylistic interpretation of prompts."
    },
    "ai4artsed_ARTS_TraditionalChinese_2506222313.json": {
        "über": "Traditionelle Chinesische Kunst\nInterpretiert Prompts nach visuellen Prinzipien einschließlich ihrer kosmologischen Hintergründe\nWendet Konzepte wie Leere, Yin-Yang und die fünf Elemente auf moderne Bildgenerierung an.",
        "info": "Traditional Chinese Art\nInterprets prompts according to visual principles including their cosmological backgrounds\nApplies concepts like emptiness, Yin-Yang and the five elements to modern image generation."
    },
    "ai4artsed_ARTS_TraditionalChinese_long_prompts_2506121345.json": {
        "über": "Traditionelle Chinesische Kunst\nInterpretiert Prompts nach visuellen Prinzipien einschließlich ihrer kosmologischen Hintergründe\nWendet Konzepte wie Leere, Yin-Yang und die fünf Elemente auf moderne Bildgenerierung an.",
        "info": "Traditional Chinese Art\nInterprets prompts according to visual principles including their cosmological backgrounds\nApplies concepts like emptiness, Yin-Yang and the five elements to modern image generation."
    },
    
    # CULTURE
    "ai4artsed_CULTURE_StillePost_2506232347.json": {
        "über": "Stille Post\nSimuliert den Stille-Post-Effekt durch mehrfache Übersetzungen\nDer Prompt durchläuft mehrere Sprachen und kehrt verändert zurück. Übersetzungsfehler und -ungenauigkeiten der Sprachmodelle werden im Bildergebnis sichtbar. Eignet sich für Spiele (wie ist es zu dem Bild gekommen)?",
        "info": "Chinese Whispers\nSimulates the Chinese whispers effect through multiple translations\nThe prompt passes through several languages and returns changed. Translation errors and inaccuracies of language models become visible in the image result. Suitable for games (how did this image come about)?"
    },
    
    # FLOW
    "ai4artsed_FLOW_ImageTextLoop_04_2506270855.json": {
        "über": "Bild-Text-Schleife (4 Iterationen)\nIterativer Prozess zwischen Bildbeschreibung und Bildgenerierung\nEin Bild wird beschrieben, die Beschreibung generiert ein neues Bild, welches wieder beschrieben wird. 4, 8 oder 16 Durchläufe.",
        "info": "Image-Text-Loop (4 iterations)\nIterative process between image description and image generation\nAn image is described, the description generates a new image, which is described again. 4, 8 or 16 cycles."
    },
    "ai4artsed_FLOW_ImageTextLoop_08_2506270855.json": {
        "über": "Bild-Text-Schleife (8 Iterationen)\nIterativer Prozess zwischen Bildbeschreibung und Bildgenerierung\nEin Bild wird beschrieben, die Beschreibung generiert ein neues Bild, welches wieder beschrieben wird. 4, 8 oder 16 Durchläufe.",
        "info": "Image-Text-Loop (8 iterations)\nIterative process between image description and image generation\nAn image is described, the description generates a new image, which is described again. 4, 8 or 16 cycles."
    },
    "ai4artsed_FLOW_ImageTextLoop_16_2506270855.json": {
        "über": "Bild-Text-Schleife (16 Iterationen)\nIterativer Prozess zwischen Bildbeschreibung und Bildgenerierung\nEin Bild wird beschrieben, die Beschreibung generiert ein neues Bild, welches wieder beschrieben wird. 4, 8 oder 16 Durchläufe.",
        "info": "Image-Text-Loop (16 iterations)\nIterative process between image description and image generation\nAn image is described, the description generates a new image, which is described again. 4, 8 or 16 cycles."
    },
    "ai4artsed_FLOW_(((PromptInterception)))_2507101853.json": {
        "über": "Prompt-Interception\nErmöglicht Erprobung von Prompt-Interception innerhalb eines Eingabefeldes\n(((Metaprompt in 3-fache Klammer setzen.))) Der Metaprompt transformiert den regulären Prompt vor der Bildgenerierung.",
        "info": "Prompt Interception\nEnables testing of prompt interception within an input field\n(((Put metaprompt in triple brackets.))) The metaprompt transforms the regular prompt before image generation."
    },
    "ai4artsed_FLOW_OmniGen2ImageEdit_2507171341.json": {
        "über": "OmniGen2 Bildbearbeitung\nNutzt OmniGen2 für instruktionsbasierte Bildbearbeitung\nVersteht natürlichsprachliche Anweisungen zur Bildmanipulation ohne Maskierung.",
        "info": "OmniGen2 Image Editing\nUses OmniGen2 for instruction-based image editing\nUnderstands natural language instructions for image manipulation without masking."
    },
    
    # INTERVENTION
    "ai4artsed_INTERVENTION_Overdrive_2506152234.json": {
        "über": "Overdrive\nInspiriert vom gleichnamigen Gitarreneffekt\nTreibt visuelle Elemente an und über ihre Grenzen. Verstärkt Farben, Kontraste und Strukturen bis zur Verzerrung.",
        "info": "Overdrive\nInspired by the guitar effect of the same name\nDrives visual elements to and beyond their limits. Amplifies colors, contrasts and structures to the point of distortion."
    },
    "ai4artsed_INTERVENTION_TheOpposite_2507122354.json": {
        "über": "Das Gegenteil\nKehrt die Bedeutung von Prompts ins Gegenteil um\nErsetzt semantische Elemente und auch ihre Beziehungen zueinander ins Gegenteil. Systematische Inversion von Konzepten.",
        "info": "The Opposite\nReverses the meaning of prompts to their opposite\nReplaces semantic elements and also their relationships to each other with opposites. Systematic inversion of concepts."
    },
    
    # INTERCEPTION  
    "ai4artsed_INTERCEPTION_Jugendsprache_2506122317.json": {
        "über": "Jugendsprache-Transformation\nÜbersetzt Prompts in aktuelle Jugendsprache\nTransformiert formelle oder neutrale Beschreibungen in die Ausdrucksweise zeitgenössischer Jugendkultur.",
        "info": "Youth Language Transformation\nTranslates prompts into current youth slang\nTransforms formal or neutral descriptions into the expression style of contemporary youth culture."
    },
    "ai4artsed_INTERCEPTION_PigLatin_2506122317.json": {
        "über": "Pig Latin Transformation\nWendet Pig-Latin-Regeln auf Prompts an\nEin spielerischer linguistischer Filter, der Wörter nach Pig-Latin-Prinzipien umformt.",
        "info": "Pig Latin Transformation\nApplies Pig Latin rules to prompts\nA playful linguistic filter that transforms words according to Pig Latin principles."
    },
    
    # MODEL
    "ai4artsed_MODEL_Flux1dev-versus-StableDiffusion3.5_2507011342.json": {
        "über": "Flux1dev vs. Stable Diffusion 3.5 vs. MetaGen2\nVergleicht drei Bildgenerierungsmodelle direkt\nGeneriert dasselbe Motiv mit drei Modellen zur direkten Gegenüberstellung ihrer Charakteristika. (MetaGen2 wird noch ergänzt)",
        "info": "Flux1dev vs. Stable Diffusion 3.5 vs. MetaGen2\nDirectly compares three image generation models\nGenerates the same motif with three models for direct comparison of their characteristics. (MetaGen2 to be added)"
    },
    "ai4artsed_MODEL_Inpainting_2507161820.json": {
        "über": "Inpainting\nFüllt ausgewählte Bildbereiche mit neuem Inhalt\nErmöglicht gezielte Bildbearbeitung durch Maskierung und Neugenerierung spezifischer Bereiche.",
        "info": "Inpainting\nFills selected image areas with new content\nEnables targeted image editing through masking and regeneration of specific areas."
    },
    "ai4artsed_MODEL_OmniGen2_2507171337.json": {
        "über": "OmniGen2\nUniverselles Bildgenerierungsmodell\nMultimodales Modell, das Text- und Bildverarbeitung für vielseitige Generierungsaufgaben kombiniert.",
        "info": "OmniGen2\nUniversal image generation model\nMultimodal model that combines text and image processing for versatile generation tasks."
    },
    "ai4artsed_MODEL_Outpainting_2507170641.json": {
        "über": "Outpainting\nErweitert Bilder über ihre ursprünglichen Grenzen hinaus\nGeneriert kohärente Fortsetzungen bestehender Bilder in alle Richtungen. Version 2 mit verbesserter Randintegration.",
        "info": "Outpainting\nExtends images beyond their original boundaries\nGenerates coherent continuations of existing images in all directions. Version 2 with improved edge integration."
    },
    "ai4artsed_MODEL_Outpainting2_2507170641.json": {
        "über": "Outpainting 2\nErweitert Bilder über ihre ursprünglichen Grenzen hinaus\nGeneriert kohärente Fortsetzungen bestehender Bilder in alle Richtungen. Version 2 mit verbesserter Randintegration.",
        "info": "Outpainting 2\nExtends images beyond their original boundaries\nGenerates coherent continuations of existing images in all directions. Version 2 with improved edge integration."
    },
    "ai4artsed_MODEL_Stable-Diffusion_3.5_TellAStory_2507152203.json": {
        "über": "Stable Diffusion 3.5 - Geschichtenerzähler\nÜbersetzt Geschichten und Gedichte in Prompts\nErweitert auch kurze Prompts zu narrativen Bildkonzepten. Spezialisiert auf die Transformation literarischer Texte.",
        "info": "Stable Diffusion 3.5 - Tell A Story\nTranslates stories and poems into prompts\nAlso expands short prompts into narrative image concepts. Specialized in transforming literary texts."
    },
    "ai4artsed_MODEL_Stable-Diffusion-3.5_2507152202.json": {
        "über": "Stable Diffusion 3.5 Standard\nBasis-Implementation des SD 3.5 Modells\nDirekter Zugang zum Stable Diffusion 3.5 Modell ohne zusätzliche Verarbeitungsschritte.",
        "info": "Stable Diffusion 3.5 Standard\nBasic implementation of the SD 3.5 model\nDirect access to the Stable Diffusion 3.5 model without additional processing steps."
    },
    
    # SOUND
    "ai4artsed_SOUND_MODEL_MusicGen_simple_2506211630.json": {
        "über": "MusicGen Einfach\nBasis-Musikgenerierung mit MusicGen\nWandelt Textbeschreibungen in Musikstücke um. Einfache, direkte Anwendung des MusicGen-Modells.",
        "info": "MusicGen Simple\nBasic music generation with MusicGen\nConverts text descriptions into music pieces. Simple, direct application of the MusicGen model."
    },
    "ai4artsed_SOUND_MODEL_StableAudio_Simple_2506291524.json": {
        "über": "Stable Audio Standard\nAudiogenerierung mit Stable Audio (auch für AceStep vorbereitet)\nErzeugt Klänge, Geräusche und kurze Musikstücke aus Textbeschreibungen. Unterstützt verschiedene Audio-Backends.",
        "info": "Stable Audio Standard\nAudio generation with Stable Audio (also prepared for AceStep)\nCreates sounds, noises and short music pieces from text descriptions. Supports various audio backends."
    },
    "ai4artsed_SOUND_MODEL_StableAudio_LongNarrativePrompts_2506291505.json": {
        "über": "Stable Audio - Geschichtenerzähler\nNarrative Audiogenerierung (auch für AceStep vorbereitet)\nOptimiert für die Erzeugung von Klanglandschaften, die Geschichten unterstützen oder erzählen. Unterstützt verschiedene Audio-Backends.",
        "info": "Stable Audio - Tell A Story\nNarrative audio generation (also prepared for AceStep)\nOptimized for creating soundscapes that support or tell stories. Supports various audio backends."
    },
    
    # VECTOR
    "ai4artsed_VECTOR_SplitAndCombineLinear_2507021805.json": {
        "über": "Lineare Vektoraufteilung\nMathematische Dekonstruktion von Bedeutungsräumen, lineare Variante\nZerlegt Prompts in Vektorkomponenten und sucht den direkten (linearen) Weg zwischen den Punkten im latenten Bedeutungsraum. Ergebnisse können überraschen oder auch konventionell ausfallen.",
        "info": "Linear Vector Split\nMathematical deconstruction of meaning spaces, linear variant\nBreaks down prompts into vector components and finds the direct (linear) path between points in latent meaning space. Results can be surprising or conventional."
    },
    "ai4artsed_VECTOR_SplitAndCombineSpherical_2507021805.json": {
        "über": "Sphärische Vektoraufteilung\nMathematische Dekonstruktion von Bedeutungsräumen, sphärische Variante\nZerlegt Prompts in Vektorkomponenten und sucht kurvige Wege zwischen den Punkten im latenten Bedeutungsraum. Tendiert zu organischeren, weniger vorhersehbaren Ergebnissen.",
        "info": "Spherical Vector Split\nMathematical deconstruction of meaning spaces, spherical variant\nBreaks down prompts into vector components and finds curved paths between points in latent meaning space. Tends towards more organic, less predictable results."
    },
    "ai4artsed_VECTOR_Surrealization_2506092253.json": {
        "über": "Surrealisierung\nVerschiebt Prompts in surreale Dimensionen\nNutzt Vektormanipulation um realistische Konzepte systematisch zu verfremden.",
        "info": "Surrealization\nShifts prompts into surreal dimensions\nUses vector manipulation to systematically alienate realistic concepts."
    },
    "ai4artsed_VECTOR_YesAndNo_V1_2506271433.json": {
        "über": "Ja und Nein V1\nErzeugt gegensätzliche Interpretationen desselben Prompts\nV1: Binäre Opposition durch Antonymersetzung. V2: Dialektische Synthese - sucht nach der Vereinigung der Gegensätze in einem Bild. Exploration von Ambivalenz und Dualität.",
        "info": "Yes and No V1\nCreates opposing interpretations of the same prompt\nV1: Binary opposition through antonym replacement. V2: Dialectical synthesis - seeks unification of opposites in one image. Exploration of ambivalence and duality."
    },
    "ai4artsed_VECTOR_YesAndNo_V2_2506271433.json": {
        "über": "Ja und Nein V2\nErzeugt gegensätzliche Interpretationen desselben Prompts\nV1: Binäre Opposition durch Antonymersetzung. V2: Dialektische Synthese - sucht nach der Vereinigung der Gegensätze in einem Bild. Exploration von Ambivalenz und Dualität.",
        "info": "Yes and No V2\nCreates opposing interpretations of the same prompt\nV1: Binary opposition through antonym replacement. V2: Dialectical synthesis - seeks unification of opposites in one image. Exploration of ambivalence and duality."
    }
}

def find_note_nodes(workflow, title):
    """Find nodes with a specific title in the workflow"""
    found_nodes = []
    for node_id, node_data in workflow.items():
        # Skip if node_data is not a dictionary
        if not isinstance(node_data, dict):
            continue
        if "_meta" in node_data and "title" in node_data["_meta"]:
            if node_data["_meta"]["title"] == title:
                found_nodes.append((node_id, node_data))
    return found_nodes

def remove_nodes(workflow, node_ids):
    """Remove nodes from workflow"""
    for node_id in node_ids:
        if node_id in workflow:
            del workflow[node_id]
            print(f"  Removed node {node_id}")

def add_or_update_nodes(workflow_path: Path, über_text: str, info_text: str):
    """Add or update über and info nodes in a workflow file"""
    
    # Read workflow
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    # Find existing nodes
    über_nodes = find_note_nodes(workflow, "über")
    about_nodes = find_note_nodes(workflow, "about")
    info_nodes = find_note_nodes(workflow, "info")
    
    # Remove existing nodes
    nodes_to_remove = []
    
    # Remove all über nodes
    for node_id, _ in über_nodes:
        nodes_to_remove.append(node_id)
    
    # Remove all about nodes (will be replaced with info)
    for node_id, _ in about_nodes:
        nodes_to_remove.append(node_id)
        
    # Remove all info nodes
    for node_id, _ in info_nodes:
        nodes_to_remove.append(node_id)
    
    if nodes_to_remove:
        print(f"  Removing {len(nodes_to_remove)} existing nodes...")
        remove_nodes(workflow, nodes_to_remove)
    
    # Find highest node ID
    max_id = 0
    for node_id in workflow.keys():
        try:
            num_id = int(node_id)
            max_id = max(max_id, num_id)
        except ValueError:
            continue
    
    # Add new nodes
    über_id = str(max_id + 1)
    info_id = str(max_id + 2)
    
    # Create nodes with correct structure
    workflow[über_id] = {
        "inputs": {
            "value": über_text
        },
        "class_type": "PrimitiveStringMultiline",
        "_meta": {
            "title": "über"
        }
    }
    
    workflow[info_id] = {
        "inputs": {
            "value": info_text
        },
        "class_type": "PrimitiveStringMultiline",
        "_meta": {
            "title": "info"
        }
    }
    
    # Write back
    with open(workflow_path, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)
    
    print(f"  Added nodes {über_id} (über) and {info_id} (info)")

def main():
    # Target directory for GUI workflows
    gui_workflows_dir = Path("/home/joerissen/ai/ai4artsed_webserver/dlbackend/ComfyUI/user/default/workflows/ai4artsed_comfyui_workflows")
    
    # Process each workflow
    success_count = 0
    error_count = 0
    not_found = []
    
    print("Starting to sync note nodes to GUI workflows...")
    print(f"Target directory: {gui_workflows_dir}\n")
    
    for filename, texts in workflow_texts.items():
        workflow_path = gui_workflows_dir / filename
        
        if workflow_path.exists():
            try:
                print(f"Processing {filename}...")
                add_or_update_nodes(workflow_path, texts["über"], texts["info"])
                success_count += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                error_count += 1
        else:
            not_found.append(filename)
    
    # Report results
    print(f"\n{'='*60}")
    print(f"Completed: {success_count} workflows updated successfully")
    print(f"Errors: {error_count}")
    print(f"Not found: {len(not_found)}")
    
    if not_found:
        print("\nWorkflows not found in GUI directory:")
        for f in not_found:
            print(f"  - {f}")

if __name__ == "__main__":
    main()
