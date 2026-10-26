export type In = { p: number; reviewMin: number; rate: number; inference: number; recovery: number; baseline: number; volume: number };
export function computeRoi(x: In) {
  const review = (x.reviewMin / 60) * x.rate;
  const failure = (1 - x.p) * x.recovery;
  const etc = x.inference + review + failure;
  const roi = etc > 0 ? (x.baseline - etc) / etc : null;
  const breakEvenP = x.recovery > 0 ? 1 - (x.baseline - x.inference - review) / x.recovery : null;
  return { review, failure, etc, roi, totalEtc: etc * x.volume, totalBaseline: x.baseline * x.volume, savings: (x.baseline - etc) * x.volume, breakEvenP };
}
