import { motion } from 'motion/react'
import { useQuote } from '../../api'
import { useUI } from '../../store'
import { EASE } from '../../theme/motion'
import CopyPromptButton from './CopyPromptButton'
import ImportedReports from './ImportedReports'

// 「研」= 复制 Prompt（喂外部网页 Deep Research）+ 导入研报回流。深度研究生成已移除，
// 改走 ChatGPT/Claude/Gemini 网页版（ADR-0011/0014/0016）。
export default function ResearchView() {
  const symbol = useUI((s) => s.selectedSymbol)
  const quote = useQuote(symbol)
  const name = quote.data?.name || ''

  if (!symbol) {
    return (
      <div className="research empty-stage">
        <div className="es-title">深度研究</div>
      </div>
    )
  }

  return (
    <motion.div
      className="research"
      key={symbol}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: EASE }}
    >
      <div className="research-head">
        <div className="rh-id">
          <h2>{name || symbol}</h2>
          <span className="rh-sym">{symbol}</span>
        </div>
        <div className="rh-actions">
          <CopyPromptButton symbol={symbol} name={name} />
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <ImportedReports symbol={symbol} />
      </div>
    </motion.div>
  )
}
