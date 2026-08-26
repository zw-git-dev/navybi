import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// Recharts measures its container to decide how big to draw. jsdom reports
// every element as 0x0, so charts would render an empty SVG and any test
// asserting on bars/lines would fail for reasons unrelated to the code under
// test. Giving ResizeObserver and the bounding box real numbers lets the
// charts actually lay out.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as never)

// jsdom implements no scrolling at all, so the scroll-to-top-on-navigate
// effect in AppShell throws. Real browsers always have this; stubbing it here
// is preferable to adding a defensive guard to app code purely to satisfy the
// test environment.
Element.prototype.scrollTo = Element.prototype.scrollTo ?? function () {}

Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
  configurable: true,
  value: function () {
    return { width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {} }
  },
})
