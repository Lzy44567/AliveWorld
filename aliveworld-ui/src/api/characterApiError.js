export class CharacterApiError extends Error {
  constructor(message, code = 'OUTCOME_UNKNOWN', retryable = false) {
    super(message); this.code = code; this.retryable = retryable;
  }
}
