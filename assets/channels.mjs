import { searchParamsFromState } from './core.mjs';
import { foreignSearchParamsFromState } from './foreign-core.mjs';

export const CHANNELS = Object.freeze({
  public: Object.freeze({
    id: 'public',
    label: '公考招录',
    dataUrl: './data/jobs.json',
    healthUrl: './data/health.json',
  }),
  foreign: Object.freeze({
    id: 'foreign',
    label: '外企校招',
    dataUrl: './data/foreign-campus.json',
    healthUrl: './data/foreign-health.json',
  }),
});

export function channelFromSearchParams(params = new URLSearchParams()) {
  return params?.get?.('channel') === 'foreign' ? 'foreign' : 'public';
}

export function searchParamsForChannel(channel, state) {
  if (channel !== 'foreign') return searchParamsFromState(state || {});
  const params = foreignSearchParamsFromState(state);
  params.set('channel', 'foreign');
  return params;
}
