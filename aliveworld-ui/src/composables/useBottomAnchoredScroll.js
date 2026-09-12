import { nextTick, ref } from 'vue';

export const useBottomAnchoredScroll = ({ threshold = 96 } = {}) => {
  const container = ref(null);
  const positioned = ref(false);
  const followsBottom = ref(true);

  const updateFollowState = () => {
    const element = container.value;
    if (!element) return;
    followsBottom.value = element.scrollHeight - element.scrollTop - element.clientHeight <= threshold;
  };

  const jumpToBottom = async ({ reveal = false, force = false } = {}) => {
    if (!force && !followsBottom.value) return;
    await nextTick();
    const element = container.value;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
    followsBottom.value = true;
    if (reveal) positioned.value = true;
  };

  const prepareAtBottom = async () => {
    positioned.value = false;
    followsBottom.value = true;
    await jumpToBottom({ reveal: true, force: true });
  };

  return { container, positioned, followsBottom, updateFollowState, jumpToBottom, prepareAtBottom };
};
