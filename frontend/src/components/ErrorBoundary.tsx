import { Component, type ErrorInfo, type ReactNode } from 'react'

// 全局错误边界：任一渲染期抛错（如某条数据形状意外、Markdown 解析越界）不再让整屏白屏，
// 而是落到一张暖纸感兜底卡，带错误摘要 + 重载。对单用户本地工具，白屏是灾难性体验。
interface Props {
  children: ReactNode
  /** 给定时，key 变化会重置错误态（如按 view 重置，使单视图崩溃不拖垮顶栏导航）。 */
  resetKey?: unknown
}
interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 仅本地 console，绝不外发（§11 本地优先且私密、无遥测）
    console.error('[Augur] 渲染出错：', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div className="errboundary">
        <div className="eb-card">
          <div className="eb-title">出了点问题</div>
          <div className="eb-msg">{error.message || '未知错误'}</div>
          <button className="btn btn-primary jsm" onClick={() => location.reload()}>
            重新加载
          </button>
        </div>
      </div>
    )
  }
}
