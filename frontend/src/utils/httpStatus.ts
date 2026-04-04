type HttpStatusKind = 'informational' | 'success' | 'redirect' | 'clientError' | 'serverError' | 'unknown'

interface HttpStatusTip {
  title: string
  meaning: string
  represents: string
  scenarios: string[]
}

const COMMON_HTTP_STATUS_TIPS: Record<number, HttpStatusTip> = {
  100: {
    title: '100 继续处理',
    meaning: '服务器已经收到请求头，客户端可以继续发送请求体。',
    represents: '请求还在继续传输，尚未得到最终结果。',
    scenarios: ['大文件上传', 'Expect: 100-continue 握手', '分段提交前的确认'],
  },
  101: {
    title: '101 切换协议',
    meaning: '服务器同意把当前连接切换到其他协议。',
    represents: '通常出现在 WebSocket 或协议升级场景。',
    scenarios: ['WebSocket 握手', 'HTTP 升级连接', '长连接协议切换'],
  },
  102: {
    title: '102 正在处理',
    meaning: '服务器已接受请求，但任务还在处理过程中。',
    represents: '本次请求没有失败，只是还没完成。',
    scenarios: ['长耗时查询', '后台计算', '批量任务处理中'],
  },
  200: {
    title: '200 成功',
    meaning: '请求成功，服务器正常返回了结果。',
    represents: '接口工作正常，通常说明参数、权限和后端都没有明显问题。',
    scenarios: ['查询成功', '列表加载正常', '数据读取或提交成功'],
  },
  201: {
    title: '201 已创建',
    meaning: '请求成功，并且服务器创建了新的资源。',
    represents: '常见于新增、创建、上传完成等动作。',
    scenarios: ['新增记录', '创建任务', '上传文件成功'],
  },
  202: {
    title: '202 已接受',
    meaning: '服务器已经接收请求，但还在异步处理中。',
    represents: '结果未立即完成，通常要稍后再查状态。',
    scenarios: ['异步任务入队', '后台审批', '延迟执行的接口'],
  },
  203: {
    title: '203 非权威信息',
    meaning: '返回内容来自中间代理、缓存或转换层，而非原始源站。',
    represents: '响应有效，但可能经过了中间层处理。',
    scenarios: ['网关转发', '代理缓存', '内容被二次处理'],
  },
  204: {
    title: '204 无内容',
    meaning: '请求成功，但服务器没有返回正文。',
    represents: '动作完成了，但前端不需要更新响应内容。',
    scenarios: ['删除成功', '保存成功但无返回体', '仅通知状态变化'],
  },
  205: {
    title: '205 重置内容',
    meaning: '请求成功，客户端应重置当前表单或视图。',
    represents: '后端在提示前端清空输入状态。',
    scenarios: ['表单提交完成', '需要清空输入框', '页面状态重置'],
  },
  206: {
    title: '206 部分内容',
    meaning: '服务器只返回了资源的一部分。',
    represents: '常见于断点续传、范围请求或分片加载。',
    scenarios: ['视频/文件分段下载', '断点续传', 'Range 请求'],
  },
  300: {
    title: '300 多重选择',
    meaning: '资源有多个可选表示，服务器返回了选择结果。',
    represents: '通常表示内容协商存在多个可用方案。',
    scenarios: ['多语言内容', '多种资源表示', '极少见的协商分支'],
  },
  301: {
    title: '301 永久重定向',
    meaning: '资源地址已经永久迁移到新位置。',
    represents: '以后应优先使用新的 URL。',
    scenarios: ['域名迁移', '路径重构', '旧链接永久跳转'],
  },
  302: {
    title: '302 临时重定向',
    meaning: '资源临时跳转到另一个地址。',
    represents: '当前只临时变更地址，原地址以后可能恢复。',
    scenarios: ['登录后跳转', '活动页跳转', '临时维护页'],
  },
  304: {
    title: '304 未修改',
    meaning: '资源自上次请求后没有变化，可以继续使用缓存。',
    represents: '命中了缓存校验，服务器不再返回正文。',
    scenarios: ['ETag 命中', 'Last-Modified 命中', '静态资源缓存复用'],
  },
  307: {
    title: '307 临时重定向',
    meaning: '资源临时重定向，并且请求方法需要保持不变。',
    represents: '相比 302，更强调不要改动原请求方法。',
    scenarios: ['接口临时迁移', '代理层转发', '保留原方法的跳转'],
  },
  308: {
    title: '308 永久重定向',
    meaning: '资源永久重定向，并且请求方法需要保持不变。',
    represents: '这是保留请求方法的永久跳转。',
    scenarios: ['接口永久迁移', '域名固定切换', '保持方法的永久跳转'],
  },
  400: {
    title: '400 请求错误',
    meaning: '请求参数、格式或语义有问题，服务器无法正确理解。',
    represents: '优先检查请求体、参数名、JSON 格式和必填字段。',
    scenarios: ['参数缺失', 'JSON 语法错误', '字段类型不对'],
  },
  401: {
    title: '401 未认证',
    meaning: '请求缺少有效身份凭证，或者凭证已经失效。',
    represents: '当前请求需要先登录或重新获取令牌。',
    scenarios: ['token 过期', '未携带登录凭证', '需要重新授权'],
  },
  403: {
    title: '403 禁止访问',
    meaning: '服务器已经识别身份，但不允许访问目标资源。',
    represents: '问题通常不是登录，而是权限或策略拦截。',
    scenarios: ['权限不足', '角色不匹配', '策略或风控拒绝'],
  },
  404: {
    title: '404 未找到',
    meaning: '请求的资源不存在，或者路径写错了。',
    represents: '先检查 URL、路由、资源 ID 和环境配置。',
    scenarios: ['路径错误', '资源已删除', '接口地址变更'],
  },
  405: {
    title: '405 方法不允许',
    meaning: '接口存在，但不接受当前请求方法。',
    represents: 'GET、POST、PUT、DELETE 等方法用错了。',
    scenarios: ['把 GET 写成 POST', '接口只支持只读方法', '路由方法配置不匹配'],
  },
  408: {
    title: '408 请求超时',
    meaning: '服务器等待请求时超时，没有等到完整请求。',
    represents: '通常意味着网络太慢、上传太久或中间链路过慢。',
    scenarios: ['网络抖动', '大文件上传过慢', '长时间未发送完整请求'],
  },
  409: {
    title: '409 冲突',
    meaning: '请求和当前资源状态冲突，无法直接处理。',
    represents: '常见于重复提交、版本冲突或状态不一致。',
    scenarios: ['重复创建', '并发修改', '乐观锁冲突'],
  },
  410: {
    title: '410 已删除',
    meaning: '资源已永久不可用，服务器明确告诉你不要再访问。',
    represents: '比 404 更明确，表示这个资源已经下线。',
    scenarios: ['旧链接失效', '资源永久下线', '内容被明确删除'],
  },
  412: {
    title: '412 前置条件失败',
    meaning: '请求要求的前置条件没有满足。',
    represents: '通常和 ETag、版本号或条件更新有关。',
    scenarios: ['ETag 不匹配', '版本号冲突', '乐观锁校验失败'],
  },
  413: {
    title: '413 请求体过大',
    meaning: '请求内容超过服务器允许的大小限制。',
    represents: '上传文件或表单内容太大，需要缩小请求体。',
    scenarios: ['文件过大', '附件过多', '请求体超出限制'],
  },
  415: {
    title: '415 不支持的媒体类型',
    meaning: '服务器不接受当前的 Content-Type 或数据格式。',
    represents: '请求格式可能和接口要求不一致。',
    scenarios: ['Content-Type 错误', '文件格式不支持', '编码方式不匹配'],
  },
  422: {
    title: '422 语义校验未通过',
    meaning: '请求格式可能没问题，但业务校验或语义规则未通过。',
    represents: '服务器看懂了请求，却不能按当前业务规则处理。',
    scenarios: ['表单校验失败', '字段缺失或非法', '业务规则冲突'],
  },
  429: {
    title: '429 请求过多',
    meaning: '请求频率超过了接口或网关的限制。',
    represents: '当前触发了限流，需要降低频率或稍后再试。',
    scenarios: ['频繁刷新', '接口限流', '达到并发上限'],
  },
  499: {
    title: '499 客户端关闭请求',
    meaning: '客户端在服务器完成响应前主动断开了连接。',
    represents: '常见于页面切换、手动取消请求或浏览器中断。',
    scenarios: ['用户切页', '请求被取消', '浏览器或代理提前断开'],
  },
  500: {
    title: '500 服务器内部错误',
    meaning: '服务器在处理请求时发生了未预期的错误。',
    represents: '通常是后端代码或运行时异常，不是请求本身简单能解决的。',
    scenarios: ['空指针异常', '未捕获错误', '后端崩溃或异常抛出'],
  },
  501: {
    title: '501 未实现',
    meaning: '服务器不支持当前所请求的功能。',
    represents: '接口能力尚未开发，或者当前部署版本还不包含该功能。',
    scenarios: ['功能未上线', '接口占位实现', '服务端暂不支持该操作'],
  },
  502: {
    title: '502 错误网关',
    meaning: '网关或代理从上游拿到了无效响应。',
    represents: '问题通常出在后端上游服务、反向代理或网关链路。',
    scenarios: ['上游服务宕机', '代理转发失败', '网关收到异常响应'],
  },
  503: {
    title: '503 服务不可用',
    meaning: '服务临时不可用，可能在维护、过载或刚刚重启。',
    represents: '通常表示服务现在忙不过来，但不一定是永久故障。',
    scenarios: ['服务维护', '流量过高', '实例刚启动或扩容中'],
  },
  504: {
    title: '504 网关超时',
    meaning: '网关等待上游服务响应时超时了。',
    represents: '链路上的后端太慢，或者超时时间设置太短。',
    scenarios: ['后端处理过慢', '依赖服务响应慢', '网关超时配置过短'],
  },
  505: {
    title: '505 HTTP 版本不支持',
    meaning: '服务器不支持当前使用的 HTTP 版本。',
    represents: '属于协议兼容问题，较少见。',
    scenarios: ['协议版本不兼容', '旧服务不支持当前协议', '中间代理限制协议'],
  },
}

const RANGE_HTTP_STATUS_TIPS: Record<HttpStatusKind, HttpStatusTip> = {
  informational: {
    title: '1xx 信息性响应',
    meaning: '服务器已经收到请求，或者请求正在进入后续处理阶段。',
    represents: '这类状态通常不是最终结果，而是过程提示。',
    scenarios: ['协议升级', '请求继续发送', '长任务处理中'],
  },
  success: {
    title: '2xx 成功响应',
    meaning: '请求已经成功被服务器处理。',
    represents: '通常说明接口、参数和后端链路都基本正常。',
    scenarios: ['查询成功', '创建成功', '删除或更新成功'],
  },
  redirect: {
    title: '3xx 重定向',
    meaning: '当前资源不在原地址，需要跳转到其他位置或继续使用缓存。',
    represents: '接口可能在迁移、临时跳转，或者命中了缓存校验。',
    scenarios: ['地址迁移', '缓存命中', '临时跳转'],
  },
  clientError: {
    title: '4xx 客户端错误',
    meaning: '请求本身存在问题，服务器无法按当前内容正确处理。',
    represents: '优先检查参数、鉴权、权限、路径和请求格式。',
    scenarios: ['参数错误', '权限不足', '资源不存在'],
  },
  serverError: {
    title: '5xx 服务器错误',
    meaning: '问题发生在服务器、网关或上游依赖。',
    represents: '通常要先看后端日志、网关状态和依赖服务健康情况。',
    scenarios: ['后端异常', '网关故障', '依赖超时或不可用'],
  },
  unknown: {
    title: '未获取到有效状态码',
    meaning: '本次请求没有拿到可用的 HTTP 响应状态。',
    represents: '这通常不是标准 HTTP 响应，更多是网络层或请求链路的问题。',
    scenarios: ['网络中断', '请求超时', '请求被取消', '跨域或浏览器拦截'],
  },
}

function resolveStatusKind(statusCode: number): HttpStatusKind {
  if (statusCode >= 100 && statusCode < 200) return 'informational'
  if (statusCode >= 200 && statusCode < 300) return 'success'
  if (statusCode >= 300 && statusCode < 400) return 'redirect'
  if (statusCode >= 400 && statusCode < 500) return 'clientError'
  if (statusCode >= 500 && statusCode < 600) return 'serverError'
  return 'unknown'
}

function resolveStatusTip(statusCode: number | null | undefined): HttpStatusTip {
  if (typeof statusCode !== 'number' || !Number.isFinite(statusCode) || statusCode <= 0) {
    return RANGE_HTTP_STATUS_TIPS.unknown
  }

  return COMMON_HTTP_STATUS_TIPS[statusCode] ?? RANGE_HTTP_STATUS_TIPS[resolveStatusKind(statusCode)]
}

export function formatHttpStatusTooltip(statusCode: number | null | undefined): string {
  const tip = resolveStatusTip(statusCode)
  return [
    tip.title,
    `含义：${tip.meaning}`,
    `代表：${tip.represents}`,
    `常见情况：${tip.scenarios.join('；')}`,
  ].join('\n')
}
