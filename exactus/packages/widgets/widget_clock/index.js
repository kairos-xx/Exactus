import "./widget_clock.js";
/** Named ES-module facade; the underlying script also supports local file demos. */
const Clock = /** @type {typeof AnalogClock} */ (
  Reflect.get(globalThis, "AnalogClock")
);
export { Clock as AnalogClock };
export default Clock;
