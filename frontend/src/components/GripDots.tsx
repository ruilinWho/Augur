// 拖拽把手：竖向 2×3 点阵（看·模块重排、导入研报排序共用）。
export default function GripDots() {
  return (
    <svg width="8" height="16" viewBox="0 0 8 16" aria-hidden="true">
      {[2.5, 5.5].flatMap((cx) =>
        [3, 8, 13].map((cy) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.05" fill="currentColor" />
        )),
      )}
    </svg>
  )
}
