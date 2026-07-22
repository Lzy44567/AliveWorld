import { reactive } from 'vue';
import { preferenceApi } from '../api/preferenceApi';

export const preferenceStore = reactive({
  preferences: [],
  analysis: {},
  pendingCount: 0,
  pendingEvidenceCount: 0,
  loading: false,
  async refresh() {
    this.loading = true;
    try {
      const data = await preferenceApi.list();
      this.preferences = data.preferences || [];
      this.analysis = data.analysis || {};
      this.pendingCount = Number(data.pending_count || 0);
      this.pendingEvidenceCount = Number(data.pending_evidence_count || 0);
      return data;
    } finally {
      this.loading = false;
    }
  }
});
