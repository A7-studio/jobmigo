export type AiRequest = {
  model: string
  system: string
  user: string
  timeoutMs?: number
}

export type AiResponse = {
  text: string
  tokensIn: number
  tokensOut: number
}

/** One model call. Adapters throw `AiUnavailableError` when the call fails. */
export interface AiProvider {
  readonly name: string
  complete: (request: AiRequest) => Promise<AiResponse>
}
