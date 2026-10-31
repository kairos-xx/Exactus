/** Pair screenshots of the same step across runs, so Compare shows a baseline and a latest capture. */
/** @typedef {{id:string,flow_id:string,event_id:string,path:string,phase:string,width:number,height:number}} Capture */
/** @typedef {{key:string,flowName:string,label:string,shots:Capture[]}} CaptureGroup */
/** Group captures by the step they show, in the order each step was first captured.
 * @param {Capture[]} screenshots Every capture in the project, oldest first.
 * @param {{id:string,name:string,events?:{id:string}[]}[]} flows Project flows.
 * @param {(event:any) => string} labelOf Name of a step.
 * @returns {CaptureGroup[]} One group per step.
 */
export const groupCaptures = (screenshots, flows, labelOf) => {
  /** @type {Map<string, CaptureGroup>} */
  const groups = new Map();
  for (const shot of screenshots) {
    const key = `${shot.flow_id}:${shot.event_id}`;
    let group = groups.get(key);
    if (!group) {
      const flow = flows.find(item => item.id === shot.flow_id);
      const event = flow?.events?.find(item => item.id === shot.event_id);
      group = {
        key,
        flowName: flow?.name ?? "Flow",
        label: event ? labelOf(event) : shot.phase,
        shots: [],
      };
      groups.set(key, group);
    }
    group.shots.push(shot);
  }
  return [...groups.values()];
};
/** Choose the step to compare and its baseline and latest captures.
 * @param {CaptureGroup[]} groups Result of `groupCaptures`.
 * @param {string} key Step the user chose, if any.
 * @returns {{group?:CaptureGroup,expected?:Capture|undefined,actual?:Capture|undefined}} A baseline exists only once a step was captured twice.
 */
export const pairFor = (groups, key) => {
  const group =
    groups.find(item => item.key === key) ??
    groups.find(item => item.shots.length > 1) ??
    groups[0];
  if (!group) return {};
  return {
    group,
    expected: group.shots.length > 1 ? group.shots[0] : undefined,
    actual: group.shots.at(-1),
  };
};
