import {
  INTERACTIVE_AUDIT_COMPOSER_MAX_WIDTH_PX,
  INTERACTIVE_AUDIT_MESSAGE_MAX_WIDTH_PERCENT,
  INTERACTIVE_AUDIT_MESSAGE_MAX_WIDTH_PX,
} from './chatLayout.constants'

describe('Interactive Audit desktop width guards', () => {
  it('keeps the composer wide enough for the authenticated workspace', () => {
    expect(INTERACTIVE_AUDIT_COMPOSER_MAX_WIDTH_PX).toBeGreaterThanOrEqual(1300)
  })

  it('keeps the message lane substantially wider than the old narrow cap', () => {
    expect(INTERACTIVE_AUDIT_MESSAGE_MAX_WIDTH_PX).toBeGreaterThanOrEqual(1200)
    expect(INTERACTIVE_AUDIT_MESSAGE_MAX_WIDTH_PERCENT).toBeGreaterThanOrEqual(90)
  })
})
