/* global process, require */
"use strict";
const fs = require("node:fs");
const { createRequire } = require("node:module");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(input.file, "utf8");
const espree = createRequire(input.file)(input.espree);
const options = {
  comment: true,
  ecmaFeatures: { jsx: true },
  ecmaVersion: "latest",
  loc: true,
  range: true,
  sourceType: "module",
  tokens: true,
};
/**
 * Parse the source as a module, falling back to script mode.
 * @returns {*} The resulting value.
 */
const parse = () => {
  try {
    return espree.parse(source, options);
  } catch (moduleError) {
    try {
      return espree.parse(source, { ...options, sourceType: "script" });
    } catch {
      throw moduleError;
    }
  }
};
const ast = parse();
const comments = [...(ast.comments ?? [])].sort((a, b) => a.range[0] - b.range[0]);
const categories = new Map([
  ["constructor", 0],
  ["public_static_accessor", 1],
  ["public_static_method", 2],
  ["public_accessor", 3],
  ["public_method", 4],
  ["private_static_accessor", 5],
  ["private_static_method", 6],
  ["private_accessor", 7],
  ["private_method", 8],
]);
/**
 * Return the member key name, preserving private `#` prefixes.
 * @param {*} node Member node.
 * @returns {string} The resulting value.
 */
const memberName = node =>
  node.key.type === "PrivateIdentifier" ? `#${node.key.name}` : String(node.key.name ?? node.key.value);
/**
 * Return the sortable category for one class member.
 * @param {*} node Member node.
 * @returns {string} The resulting value.
 */
const category = node => {
  if (node.kind === "constructor") return "constructor";
  const privacy = node.key.type === "PrivateIdentifier" ? "private" : "public";
  const binding = node.static ? "static_" : "";
  const kind = node.kind === "get" || node.kind === "set" ? "accessor" : "method";
  return `${privacy}_${binding}${kind}`;
};
/**
 * Return the source offset where a member's leading comments begin.
 * @param {*} node Member node.
 * @returns {number} The resulting value.
 */
const leadingStart = node => {
  let start = node.range[0];
  for (let index = comments.length - 1; index >= 0; index -= 1) {
    const comment = comments[index];
    if (comment.range[1] > start) continue;
    const gap = source.slice(comment.range[1], start);
    if (!/^\s*$/.test(gap) || (gap.match(/\n/g) ?? []).length > 1) break;
    start = comment.range[0];
  }
  return start;
};
/**
 * Sort one contiguous member run while keeping accessor families adjacent.
 * @param {Array<*>} run Members captured between barriers.
 * @returns {Array<*>} The resulting value.
 */
const sortRun = run => {
  const families = new Map();
  let nextFamily = 0;
  run.forEach(member => {
    if (member.node.kind !== "get" && member.node.kind !== "set") return;
    const family = `${member.node.static}:${memberName(member.node)}`;
    if (!families.has(family)) families.set(family, nextFamily++);
  });
  return [...run].sort((left, right) => {
    const leftCategory = category(left.node);
    const rightCategory = category(right.node);
    const rankDelta = (categories.get(leftCategory) ?? 0) - (categories.get(rightCategory) ?? 0);
    if (rankDelta !== 0) return rankDelta;
    if (left.node.kind === "get" || left.node.kind === "set") {
      const leftFamily = families.get(`${left.node.static}:${memberName(left.node)}`);
      const rightFamily = families.get(`${right.node.static}:${memberName(right.node)}`);
      if (leftFamily !== rightFamily) return leftFamily - rightFamily;
      const accessorDelta = (left.node.kind === "get" ? 0 : 1) - (right.node.kind === "get" ? 0 : 1);
      if (accessorDelta !== 0) return accessorDelta;
    }
    return left.index - right.index;
  });
};
/** @type {Array<*>} */
const classes = [];
/**
 * Visit structural class declarations, skipping function-local scopes.
 * @param {*} node Node.
 */
const visitStructural = node => {
  if (!node || typeof node !== "object") return;
  if (node.type === "ClassDeclaration" || node.type === "ClassExpression") {
    classes.push(node);
    /** @type {Array<*>} */
    (node.body.body).forEach(member => {
      if (member.type === "MethodDefinition" && member.value?.body) return;
      if (member.type === "PropertyDefinition") return;
      visitStructural(member);
    });
    return;
  }
  if (["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"].includes(node.type)) return;
  Object.entries(node).forEach(([key, value]) => {
    if (["comments", "loc", "range", "tokens"].includes(key)) return;
    if (Array.isArray(value)) value.forEach(visitStructural);
    else visitStructural(value);
  });
};
/**
 * Reorder safe class-method runs and report movement metrics.
 * @returns {*} The organize payload.
 */
const organize = () => {
  visitStructural(ast);
  let output = source;
  let classesSeen = 0;
  let classesReordered = 0;
  let methodsSeen = 0;
  let methodsMoved = 0;
  let linesMoved = 0;
  /** @type {Array<[number, number, string]>} */
  const replacements = [];
  classes.sort((a, b) => b.range[0] - a.range[0]).forEach(classNode => {
    classesSeen += 1;
    /** @type {Array<*>} */
    let run = [];
    let classChanged = false;
    /**
     * Close the current movable run, recording replacements when the
     * canonically ordered members differ from their original order.
     */
    const flush = () => {
      if (run.length < 2) {
        methodsSeen += run.length;
        run = [];
        return;
      }
      methodsSeen += run.length;
      const ordered = sortRun(run);
      const moved = run.filter((member, index) => member.node !== ordered[index].node).length;
      if (moved === 0) {
        run = [];
        return;
      }
      classChanged = true;
      methodsMoved += moved;
      run.forEach((slot, index) => {
        const replacement = ordered[index];
        const text = source.slice(replacement.start, replacement.node.range[1]);
        replacements.push([slot.start, slot.node.range[1], text]);
        if (slot.node !== replacement.node) linesMoved += (text.match(/\n/g) ?? []).length + 1;
      });
      run = [];
    };
    /** @type {Array<*>} */
    (classNode.body.body).forEach((node, index) => {
      if (node.type === "MethodDefinition" && !node.computed) {
        run.push({ node, index, start: leadingStart(node) });
        return;
      }
      flush();
    });
    flush();
    if (classChanged) classesReordered += 1;
  });
  replacements.sort((a, b) => b[0] - a[0]).forEach(([start, end, text]) => {
    output = output.slice(0, start) + text + output.slice(end);
  });
  return {
    source: output,
    metrics: {
      classes_reordered: classesReordered,
      classes_seen: classesSeen,
      lines_moved: linesMoved,
      methods_moved: methodsMoved,
      methods_seen: methodsSeen,
    },
  };
};
const ignoredKeys = new Set([
  "comments",
  "end",
  "loc",
  "parent",
  "range",
  "start",
  "tokens",
]);
/**
 * Return whether node.
 * @param {*} value Value.
 */
const isNode = value =>
  value !== null && typeof value === "object" && typeof value.type === "string";
/**
 * Handle children.
 * @param {*} node Node.
 */
const children = node =>
  Object.entries(node)
    .filter(([key]) => !ignoredKeys.has(key))
    .flatMap(([, value]) =>
      Array.isArray(value)
        ? value.filter(isNode)
        : isNode(value)
          ? [value]
          : [],
    );
/**
 * Return key name.
 * @param {*} key Key.
 * @param {boolean} computed Computed.
 * @returns {*} The resulting value.
 */
const keyName = (key, computed = false) => {
  if (!key) return "<anonymous>";
  if (computed) return source.slice(key.range[0], key.range[1]);
  if (key.type === "Identifier" || key.type === "PrivateIdentifier")
    return key.name;
  if (key.type === "Literal") return String(key.value);
  return source.slice(key.range[0], key.range[1]);
};
/**
 * Return inferred name.
 * @param {*} node Node.
 * @param {*} parent Parent.
 * @returns {*} The resulting value.
 */
const inferredName = (node, parent) => {
  if (node.id?.name) return node.id.name;
  if (!parent) return "<anonymous>";
  if (
    parent.type === "VariableDeclarator" &&
    parent.init === node &&
    parent.id.type === "Identifier"
  )
    return parent.id.name;
  if (parent.type === "AssignmentExpression" && parent.right === node) {
    if (parent.left.type === "Identifier") return parent.left.name;
    if (
      parent.left.type === "MemberExpression" &&
      !parent.left.computed &&
      parent.left.property.type === "Identifier"
    )
      return parent.left.property.name;
  }
  if (parent.type === "Property" && parent.value === node)
    return keyName(parent.key, parent.computed);
  if (parent.type === "PropertyDefinition" && parent.value === node)
    return keyName(parent.key, parent.computed);
  return "<anonymous>";
};
/**
 * Handle class name.
 * @param {*} node Node.
 * @param {*} parent Parent.
 */
const className = (node, parent) =>
  node.id?.name ??
  (parent?.type === "VariableDeclarator" && parent.id.type === "Identifier"
    ? parent.id.name
    : "<anonymous class>");
/**
 * Return contains direct semantic use.
 * @param {*} fn Fn.
 * @param {*} wanted Wanted.
 * @returns {*} The resulting value.
 */
const containsDirectSemanticUse = (fn, wanted) => {
  let found = false;
  /**
   * Handle visit.
   * @param {*} node Node.
   */
  const visit = node => {
    if (!isNode(node) || found) return;
    if (
      node !== fn &&
      (node.type === "FunctionDeclaration" ||
        node.type === "FunctionExpression")
    )
      return;
    if (
      node !== fn &&
      (node.type === "ClassDeclaration" || node.type === "ClassExpression")
    )
      return;
    if (wanted(node)) {
      found = true;
      return;
    }
    children(node).forEach(visit);
  };
  visit(fn.body ?? fn);
  return found;
};
/**
 * Handle uses receiver.
 * @param {*} fn Fn.
 */
const usesReceiver = fn =>
  containsDirectSemanticUse(
    fn,
    /** @param {*} node */
    node => node.type === "ThisExpression" || node.type === "Super",
  );
/**
 * Handle uses arguments.
 * @param {*} fn Fn.
 */
const usesArguments = fn =>
  containsDirectSemanticUse(
    fn,
    /** @param {*} node */
    node => node.type === "Identifier" && node.name === "arguments",
  );
/**
 * Handle uses new target.
 * @param {*} fn Fn.
 */
const usesNewTarget = fn =>
  containsDirectSemanticUse(
    fn,
    /** @param {*} node */
    node =>
      node.type === "MetaProperty" &&
      node.meta?.name === "new" &&
      node.property?.name === "target",
  );
/**
 * Return whether yield.
 * @param {*} fn Fn.
 */
const hasYield = fn =>
  containsDirectSemanticUse(
    fn,
    /** @param {*} node */
    node => node.type === "YieldExpression",
  );
/**
 * Handle source text.
 * @param {*} node Node.
 */
const sourceText = node => source.slice(node.range[0], node.range[1]);
/**
 * Return blockers caused by ordinary-function identity or program usage.
 * @param {*} fn Function node.
 * @returns {string[]} Semantic blockers.
 */
const identityBlockersFor = fn => {
  if (fn.type === "FunctionExpression" && fn.id?.name)
    return ["named function expression"];
  if (fn.type !== "FunctionDeclaration" || !fn.id?.name) return [];
  const name = fn.id.name;
  const blockers = new Set();
  /**
   * Visit descendants while tracking the owning function.
   * @param {*} node AST node.
   * @param {*} owner Owning function node.
   */
  const visit = (node, owner = null) => {
    if (!isNode(node)) return;
    if (node !== fn) {
      if (
        node.type === "NewExpression" &&
        node.callee?.type === "Identifier" &&
        node.callee.name === name
      )
        blockers.add("constructible/new");
      if (
        node.type === "MemberExpression" &&
        node.object?.type === "Identifier" &&
        node.object.name === name &&
        ((!node.computed && node.property?.name === "prototype") ||
          (node.computed && node.property?.value === "prototype"))
      )
        blockers.add("prototype");
      if (
        node.type === "CallExpression" &&
        node.callee?.type === "MemberExpression" &&
        node.callee.object?.type === "Identifier" &&
        node.callee.object.name === "Object" &&
        node.callee.property?.name === "hasOwn" &&
        node.arguments?.[0]?.type === "Identifier" &&
        node.arguments[0].name === name &&
        node.arguments?.[1]?.type === "Literal" &&
        node.arguments[1].value === "prototype"
      )
        blockers.add("prototype");
      if (
        node.type === "VariableDeclarator" &&
        node.init?.type === "Identifier" &&
        node.init.name === name &&
        node.id?.type === "Identifier"
      ) {
        const alias = node.id.name;
        /**
         * Visit an alias reference.
         * @param {*} candidate Candidate AST node.
         */
        const aliasVisit = candidate => {
          if (!isNode(candidate)) return;
          if (
            candidate.type === "NewExpression" &&
            candidate.callee?.type === "Identifier" &&
            candidate.callee.name === alias
          )
            blockers.add("constructible/new");
          children(candidate).forEach(aliasVisit);
        };
        aliasVisit(ast);
      }
      if (
        node.type === "Identifier" &&
        node.name === name &&
        node.range?.[0] < fn.range[0] &&
        !(owner?.type === "FunctionDeclaration" && owner.id === node)
      )
        blockers.add("declaration hoisting");
    }
    children(node).forEach(child => {
      visit(child, node);
    });
  };
  visit(ast);
  return [...blockers];
};
/**
 * Build one analyzer result block.
 * @param {{node: *, fn: *, kind: string, name: string, ownerClass?: string|null, isStatic?: boolean, methodKind?: string|null, parent?: *}} value Block inputs.
 * @returns {*} The analyzer result block.
 */
const makeBlock = value => {
  const {
    node,
    fn,
    kind,
    name,
    ownerClass = null,
    isStatic = false,
    methodKind = null,
  } = value;
  const arrowCurrent = fn.type === "ArrowFunctionExpression";
  const receiver = usesReceiver(fn);
  const argumentsUse = usesArguments(fn);
  const newTargetUse = usesNewTarget(fn);
  const yieldUse = hasYield(fn);
  const generator = Boolean(fn.generator);
  const constructor = methodKind === "constructor";
  const getter = methodKind === "get";
  const setter = methodKind === "set";
  const methodLike = kind === "method" || kind === "class_field";
  const identityBlockers = identityBlockersFor(fn);
  const staticEligible =
    methodLike && !isStatic && !constructor && !getter && !setter && !receiver;
  const arrowBlockers = [];
  if (constructor) arrowBlockers.push("constructor");
  if (getter) arrowBlockers.push("getter");
  if (setter) arrowBlockers.push("setter");
  if (generator || yieldUse) arrowBlockers.push("generator/yield");
  if (receiver && !arrowCurrent) arrowBlockers.push("dynamic this/super");
  if (argumentsUse && !arrowCurrent) arrowBlockers.push("arguments");
  if (newTargetUse && !arrowCurrent) arrowBlockers.push("new.target");
  if (!arrowCurrent) arrowBlockers.push(...identityBlockers);
  const arrowEligible = arrowCurrent || arrowBlockers.length === 0;
  let recommendation = "keep";
  if (staticEligible && arrowEligible) recommendation = "make static arrow";
  else if (staticEligible) recommendation = "make static";
  else if (
    isStatic &&
    !arrowCurrent &&
    arrowEligible &&
    !constructor &&
    !getter &&
    !setter
  )
    recommendation = "use static arrow";
  else if (!methodLike && !arrowCurrent && arrowEligible)
    recommendation = "use arrow";
  return {
    arrow_blockers: arrowBlockers,
    arrow_current: arrowCurrent,
    arrow_eligible: arrowEligible,
    async: Boolean(fn.async),
    class_name: ownerClass,
    column_end: node.loc.end.column + 1,
    column_start: node.loc.start.column + 1,
    kind,
    line_end: node.loc.end.line,
    line_start: node.loc.start.line,
    method_kind: methodKind,
    name,
    recommendation,
    source: sourceText(node),
    static_current: isStatic,
    static_eligible: staticEligible,
    uses_arguments: argumentsUse,
    uses_new_target: newTargetUse,
    uses_this_or_super: receiver,
  };
};
/** @type {Array<*>} */
const blocks = [];
/** @type {string[]} */
const classStack = [];
/**
 * Handle walk.
 * @param {*} node Node.
 * @param {*} parent Parent.
 */
const walk = (node, parent = null) => {
  if (!isNode(node)) return;
  const isClass =
    node.type === "ClassDeclaration" || node.type === "ClassExpression";
  if (isClass) classStack.push(className(node, parent));
  if (node.type === "MethodDefinition")
    blocks.push(
      makeBlock({
        node,
        fn: node.value,
        kind: "method",
        name: keyName(node.key, node.computed),
        ownerClass: classStack.at(-1) ?? null,
        isStatic: Boolean(node.static),
        methodKind: node.kind ?? "method",
        parent,
      }),
    );
  else if (
    node.type === "PropertyDefinition" &&
    node.value &&
    (node.value.type === "ArrowFunctionExpression" ||
      node.value.type === "FunctionExpression")
  )
    blocks.push(
      makeBlock({
        node,
        fn: node.value,
        kind: "class_field",
        name: keyName(node.key, node.computed),
        ownerClass: classStack.at(-1) ?? null,
        isStatic: Boolean(node.static),
        methodKind: "field",
        parent,
      }),
    );
  else if (node.type === "FunctionDeclaration")
    blocks.push(
      makeBlock({
        node,
        fn: node,
        kind: "function_declaration",
        name: inferredName(node, parent),
        parent,
      }),
    );
  else if (
    node.type === "FunctionExpression" &&
    parent?.type !== "MethodDefinition" &&
    parent?.type !== "PropertyDefinition" &&
    !(parent?.type === "Property" && parent.method)
  )
    blocks.push(
      makeBlock({
        node,
        fn: node,
        kind: "function_expression",
        name: inferredName(node, parent),
        parent,
      }),
    );
  else if (node.type === "Property" && node.method && node.kind === "init")
    blocks.push(
      makeBlock({
        node,
        fn: node.value,
        kind: "object_method",
        name: keyName(node.key, node.computed),
        methodKind: "method",
        parent,
      }),
    );
  else if (
    node.type === "ArrowFunctionExpression" &&
    parent?.type !== "PropertyDefinition"
  )
    blocks.push(
      makeBlock({
        node,
        fn: node,
        kind: "arrow_function",
        name: inferredName(node, parent),
        parent,
      }),
    );
  children(node).forEach(child => {
    walk(child, node);
  });
  if (isClass) classStack.pop();
};
/**
 * Emit the function-block analysis report.
 * @returns {*} The analyze payload.
 */
const analyze = () => {
  walk(ast);
  blocks.sort(
    (left, right) =>
      left.line_start - right.line_start ||
      left.column_start - right.column_start ||
      left.line_end - right.line_end,
  );
  return blocks;
};
/**
 * Handle params text.
 * @param {*} fn Fn.
 */
const paramsText = fn =>
  fn.params.map(/** @param {*} param */ param => sourceText(param));
/**
 * Return arrow params.
 * @param {*} fn Fn.
 * @returns {*} The resulting value.
 */
const arrowParams = fn => {
  const params = paramsText(fn);
  return params.length === 1 && fn.params[0].type === "Identifier"
    ? params[0]
    : `(${params.join(", ")})`;
};
/**
 * Handle ordinary params.
 * @param {*} fn Fn.
 */
const ordinaryParams = fn => `(${paramsText(fn).join(", ")})`;
/**
 * Return compact arrow body.
 * @param {*} fn Fn.
 * @returns {*} The resulting value.
 */
const compactArrowBody = fn => {
  if (
    fn.body.type === "BlockStatement" &&
    fn.body.body.length === 1 &&
    fn.body.body[0].type === "ReturnStatement" &&
    fn.body.body[0].argument
  ) {
    const expression = sourceText(fn.body.body[0].argument);
    return fn.body.body[0].argument.type === "ObjectExpression"
      ? `(${expression})`
      : expression;
  }
  return sourceText(fn.body);
};
/**
 * Handle arrow text.
 * @param {*} fn Fn.
 */
const arrowText = fn =>
  `${fn.async ? "async " : ""}${arrowParams(fn)} => ${compactArrowBody(fn)}`;
/**
 * Return function text.
 * @param {*} fn Fn.
 * @returns {*} The resulting value.
 */
const functionText = fn => {
  const body =
    fn.body.type === "BlockStatement"
      ? sourceText(fn.body)
      : `{ return ${sourceText(fn.body)}; }`;
  return `${fn.async ? "async " : ""}function${ordinaryParams(fn)} ${body}`;
};
/**
 * Return method text.
 * @param {*} node Node.
 * @param {*} fn Fn.
 * @returns {*} The resulting value.
 */
const methodText = (node, fn) => {
  const body =
    fn.body.type === "BlockStatement"
      ? sourceText(fn.body)
      : `{ return ${sourceText(fn.body)}; }`;
  return (
    `${node.static ? "static " : ""}${fn.async ? "async " : ""}` +
    `${keyName(node.key, node.computed)}${ordinaryParams(fn)} ${body}`
  );
};
/**
 * Handle edit.
 * @param {*} node Node.
 * @param {*} replacement Replacement.
 */
const edit = (node, replacement) => ({
  end: node.range[1],
  replacement,
  start: node.range[0],
});
/**
 * Return an edit converting a function to an arrow function.
 * @param {*} node Node.
 * @param {*} parent Parent.
 * @param {boolean} [automatic] Whether automatic conversion is enabled.
 * @returns {*} The resulting edit, or null when conversion is unsafe.
 */
const toArrowEdit = (node, parent, automatic = false) => {
  if (node.type === "MethodDefinition") {
    if (automatic && !node.static) return null;
    const fn = node.value;
    const receiver = usesReceiver(fn);
    if (
      node.kind === "constructor" ||
      node.kind === "get" ||
      node.kind === "set" ||
      fn.generator ||
      hasYield(fn) ||
      usesArguments(fn) ||
      usesNewTarget(fn) ||
      receiver
    )
      return null;
    return edit(
      node,
      `${node.static || !receiver ? "static " : ""}` +
        `${keyName(node.key, node.computed)} = ${arrowText(fn)};`,
    );
  }
  if (
    node.type === "PropertyDefinition" &&
    node.value?.type === "FunctionExpression"
  ) {
    const fn = node.value;
    if (
      fn.generator ||
      hasYield(fn) ||
      usesReceiver(fn) ||
      usesArguments(fn) ||
      usesNewTarget(fn)
    )
      return null;
    return edit(
      node,
      `${node.static ? "static " : ""}` +
        `${keyName(node.key, node.computed)} = ${arrowText(fn)};`,
    );
  }
  if (node.type === "FunctionDeclaration" && node.id) {
    if (
      node.generator ||
      hasYield(node) ||
      usesReceiver(node) ||
      usesArguments(node) ||
      usesNewTarget(node) ||
      identityBlockersFor(node).length > 0
    )
      return null;
    return edit(node, `const ${node.id.name} = ${arrowText(node)};`);
  }
  if (
    node.type === "FunctionExpression" &&
    parent?.type !== "MethodDefinition" &&
    parent?.type !== "PropertyDefinition" &&
    !(
      parent?.type === "Property" &&
      (parent.method || parent.kind !== "init")
    )
  ) {
    if (
      node.generator ||
      hasYield(node) ||
      usesReceiver(node) ||
      usesArguments(node) ||
      usesNewTarget(node) ||
      identityBlockersFor(node).length > 0
    )
      return null;
    return edit(node, arrowText(node));
  }
  if (node.type === "Property" && node.method && node.kind === "init") {
    const fn = node.value;
    if (
      fn.generator ||
      hasYield(fn) ||
      usesReceiver(fn) ||
      usesArguments(fn) ||
      usesNewTarget(fn)
    )
      return null;
    return edit(node, `${keyName(node.key, node.computed)}: ${arrowText(fn)}`);
  }
  return null;
};
/**
 * Return from arrow edit.
 * @param {*} node Node.
 * @param {*} parent Parent.
 * @returns {*} The resulting value.
 */
const fromArrowEdit = (node, parent) => {
  if (
    node.type === "PropertyDefinition" &&
    node.value?.type === "ArrowFunctionExpression"
  ) {
    const fn = node.value;
    if (usesReceiver(fn) || usesArguments(fn) || usesNewTarget(fn)) return null;
    return edit(node, methodText(node, fn));
  }
  if (
    node.type === "ArrowFunctionExpression" &&
    parent?.type !== "PropertyDefinition"
  ) {
    if (usesReceiver(node) || usesArguments(node) || usesNewTarget(node))
      return null;
    return edit(node, functionText(node));
  }
  return null;
};
/**
 * Collect edits.
 * @param {*} direction Direction.
 * @returns {*} The resulting value.
 */
const collectEdits = direction => {
  /** @type {Array<{start: number, end: number, replacement: string}>} */
  const edits = [];
  /**
   * Handle visit.
   * @param {*} node Node.
   * @param {*} parent Parent.
   */
  const visit = (node, parent = null) => {
    if (!isNode(node)) return;
    const candidate =
      direction === "to_arrow"
        ? toArrowEdit(node, parent)
        : direction === "normalize"
          ? toArrowEdit(node, parent, true)
          : fromArrowEdit(node, parent);
    if (candidate) {
      edits.push(candidate);
      return;
    }
    children(node).forEach(child => {
      visit(child, node);
    });
  };
  visit(ast);
  return edits;
};
/**
 * Handle apply edits.
 * @param {*} edits Edits.
 */
const applyEdits = edits =>
  edits
    .sort(
      /** @param {*} left @param {*} right */ (left, right) =>
        right.start - left.start,
    )
    .reduce(
      /** @param {string} text @param {*} current */
      (text, current) =>
        text.slice(0, current.start) +
        current.replacement +
        text.slice(current.end),
      source,
    );
if (input.action === "convert") {
  if (
    input.direction !== "to_arrow" &&
    input.direction !== "from_arrow" &&
    input.direction !== "normalize"
  )
    throw new Error(`Unsupported conversion direction: ${input.direction}`);
  const edits = collectEdits(input.direction);
  const converted = applyEdits(edits);
  process.stdout.write(
    JSON.stringify({
      changed: converted !== source,
      source: converted,
      transformations: edits.length,
    }),
  );
} else if (input.action === "analyze")
  process.stdout.write(JSON.stringify(analyze()));
 else
  process.stdout.write(JSON.stringify(organize()));
