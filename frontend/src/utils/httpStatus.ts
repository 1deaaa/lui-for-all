import { translate, translateMessages } from '@/i18n'

type HttpStatusKind = 'informational' | 'success' | 'redirect' | 'clientError' | 'serverError' | 'unknown'

interface HttpStatusTip {
  title: string
  meaning: string
  represents: string
  scenarios: string[]
}

interface HttpStatusMessages {
  unknown?: Partial<HttpStatusTip>
  kinds?: Partial<Record<HttpStatusKind, Partial<HttpStatusTip>>>
  codes?: Record<string, Partial<HttpStatusTip>>
}

function resolveStatusKind(statusCode: number): HttpStatusKind {
  if (statusCode >= 100 && statusCode < 200) return 'informational'
  if (statusCode >= 200 && statusCode < 300) return 'success'
  if (statusCode >= 300 && statusCode < 400) return 'redirect'
  if (statusCode >= 400 && statusCode < 500) return 'clientError'
  if (statusCode >= 500 && statusCode < 600) return 'serverError'
  return 'unknown'
}

function normalizeTip(raw: Partial<HttpStatusTip> | undefined): HttpStatusTip {
  return {
    title: raw?.title ?? '',
    meaning: raw?.meaning ?? '',
    represents: raw?.represents ?? '',
    scenarios: Array.isArray(raw?.scenarios) ? raw!.scenarios! : [],
  }
}

function getStatusMessages(): HttpStatusMessages {
  return translateMessages<HttpStatusMessages>('httpStatus') || {}
}

function resolveStatusTip(statusCode: number | null | undefined): HttpStatusTip {
  const messages = getStatusMessages()

  if (typeof statusCode !== 'number' || !Number.isFinite(statusCode) || statusCode <= 0) {
    return normalizeTip(messages.unknown)
  }

  const exact = messages.codes?.[String(statusCode)]
  if (exact) {
    return normalizeTip(exact)
  }

  const kind = resolveStatusKind(statusCode)
  return normalizeTip(messages.kinds?.[kind] ?? messages.unknown)
}

export function formatHttpStatusTooltip(statusCode: number | null | undefined): string {
  const tip = resolveStatusTip(statusCode)
  const meaningLabel = translate('httpStatus.sections.meaning')
  const representsLabel = translate('httpStatus.sections.represents')
  const scenariosLabel = translate('httpStatus.sections.scenarios')
  const scenarios = tip.scenarios.length > 0 ? tip.scenarios.join('；') : '-'

  return [
    tip.title,
    `${meaningLabel}: ${tip.meaning}`,
    `${representsLabel}: ${tip.represents}`,
    `${scenariosLabel}: ${scenarios}`,
  ].join('\n')
}
