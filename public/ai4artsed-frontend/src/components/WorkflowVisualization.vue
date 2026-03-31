<template>
  <div class="workflow-container">
    <h3 class="workflow-title">{{ $t('status.executing') }}</h3>

    <div class="workflow-boxes">
      <TransitionGroup name="slide-fade">
        <div
          v-for="stage in visibleStages"
          :key="stage.id"
          class="stage-box"
          :class="stage.status"
        >
          <div class="stage-icon">{{ stage.icon }}</div>
          <div class="stage-content">
            <div class="stage-name">{{ $t(`stages.${stage.id}`) }}</div>
            <div v-if="stage.progress !== null" class="stage-progress">
              {{ stage.progress }}%
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <div v-if="statusMessage" class="status-message" :class="statusType">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'WorkflowVisualization',
  props: {
    stages: {
      type: Array,
      default: () => []
    },
    statusMessage: {
      type: String,
      default: ''
    },
    statusType: {
      type: String,
      default: 'info'
    }
  },
  computed: {
    visibleStages() {
      return this.stages.map(stage => ({
        ...stage,
        icon: this.getStageIcon(stage.id)
      }))
    }
  },
  methods: {
    getStageIcon(stageId) {
      const icons = {
        pipeline_starting: '1',
        translation_and_safety: '2',
        interception: '3',
        pre_output_safety: '4',
        media_generation: '5',
        completed: '✓'
      }
      return icons[stageId] || '—'
    }
  }
}
</script>

<style scoped>
.workflow-container {
  margin: 2rem 0;
}

.workflow-title {
  text-align: center;
  font-size: 1.2rem;
  margin-bottom: 1.5rem;
  color: #333;
}

.workflow-boxes {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: center;
  align-items: flex-start;
  min-height: 200px;
}

.stage-box {
  background: #f8f9fa;
  border: 2px solid #dee2e6;
  border-radius: 8px;
  padding: 1rem;
  min-width: 150px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  transition: all 0.3s ease;
}

.stage-box.active {
  background: #e3f2fd;
  border-color: #2196f3;
  box-shadow: 0 4px 12px rgba(33, 150, 243, 0.2);
}

.stage-box.completed {
  background: #e8f5e9;
  border-color: #4caf50;
}

.stage-icon {
  font-size: 2rem;
  line-height: 1;
}

.stage-content {
  flex: 1;
}

.stage-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: #333;
  margin-bottom: 0.25rem;
}

.stage-progress {
  font-size: 0.85rem;
  color: #666;
  font-weight: 500;
}

.status-message {
  text-align: center;
  padding: 0.75rem;
  margin-top: 1.5rem;
  border-radius: 6px;
  font-weight: 500;
}

.status-message.info {
  background: #e3f2fd;
  color: #1976d2;
}

.status-message.warning {
  background: #fff3e0;
  color: #f57c00;
}

.status-message.success {
  background: #e8f5e9;
  color: #388e3c;
}

.status-message.error {
  background: #ffebee;
  color: #d32f2f;
}

/* Vue Transition Animations */
.slide-fade-enter-active {
  transition: all 0.5s ease;
}

.slide-fade-leave-active {
  transition: all 0.3s ease;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(-30px) scale(0.9);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(30px) scale(0.9);
}

.slide-fade-move {
  transition: transform 0.5s ease;
}
</style>
