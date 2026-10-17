/**
 * How the providers are written — one spelling, for every surface that names one.
 *
 * Two maps carried this before, and neither was complete: the API management tab
 * knew IONOS and Mammouth AI, the backend status tab knew AWS Bedrock. Whatever a
 * map was missing fell through to the raw key, so the backend status table read
 * "ionos" and "mammouth" in a column that otherwise said "Mistral AI" and
 * "OpenAI".
 *
 * These are the providers' own spellings, not translatable copy.
 */
export const PROVIDER_NAMES: Record<string, string> = {
  mammouth: 'Mammouth AI',
  mistral: 'Mistral AI',
  ionos: 'IONOS',
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  aws_bedrock: 'AWS Bedrock',
  // The register writes the same service without the vendor (hardware_matrix
  // llm_presets.bedrock); the api-usage route writes it with.
  bedrock: 'AWS Bedrock',
}

/** The provider's own spelling; an unknown key is shown as it arrived. */
export function providerName(key: string): string {
  return PROVIDER_NAMES[key] ?? key
}
