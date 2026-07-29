import { computed, reactive } from 'vue';
import { connectionApi } from '../api/connectionApi';

export const connectionStore = reactive({
  profiles: [],
  routes: {},
  schemaVersion: 1,
  loading: false,
  loaded: false,

  async refresh() {
    this.loading = true;
    try {
      const data = await connectionApi.list();
      this.profiles = Array.isArray(data.profiles) ? data.profiles : [];
      this.routes = data.routes || {};
      this.schemaVersion = data.schema_version || 1;
      this.loaded = true;
      return data;
    } finally {
      this.loading = false;
    }
  },

  async create(payload) {
    const profile = await connectionApi.create(payload);
    await this.refresh();
    return profile;
  },

  async update(id, payload) {
    const profile = await connectionApi.update(id, payload);
    await this.refresh();
    return profile;
  },

  async clone(id, name) {
    const profile = await connectionApi.clone(id, name);
    await this.refresh();
    return profile;
  },

  async remove(id) {
    await connectionApi.remove(id);
    await this.refresh();
  },

  async test(id) {
    const result = await connectionApi.test(id);
    await this.refresh();
    return result;
  },

  async reveal(id) {
    return connectionApi.reveal(id);
  },

  async setRoute(task, payload) {
    const route = await connectionApi.setRoute(task, payload);
    await this.refresh();
    return route;
  },
});

export const profileById = computed(() =>
  Object.fromEntries(connectionStore.profiles.map(profile => [profile.id, profile])),
);
