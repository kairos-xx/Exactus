/* global exports */
"use strict";
/**
 * Return loc.
 * @param {*} source Source.
 * @param {*} start Start.
 * @param {*} end End.
 * @returns {*} The resulting value.
 */
const loc = (source, start, end) => {
  /**
   * Return position.
   * @param {*} offset Offset.
   * @returns {*} The resulting value.
   */
  const position = offset => {
    const before = source.slice(0, offset).split("\n");
    return {
      line: before.length,
      column: before.at(-1).length,
    };
  };
  return {
    start: position(start),
    end: position(end),
  };
};
/**
 * Return node.
 * @param {*} source Source.
 * @param {*} type Type.
 * @param {*} text Text.
 * @param {Object} extra Extra.
 * @param {number} from From.
 * @returns {*} The resulting value.
 * @throws {Error} When the operation cannot complete.
 */
const node = (source, type, text, extra = {}, from = 0) => {
  const start = source.indexOf(text, from);
  if (start < 0) throw new Error(`Fixture text not found: ${text}`);
  const end = start + text.length;
  return {
    type,
    range: [start, end],
    loc: loc(source, start, end),
    ...extra,
  };
};
/**
 * Handle identifier.
 * @param {*} source Source.
 * @param {*} name Name.
 * @param {number} from From.
 */
const identifier = (source, name, from = 0) =>
  node(
    source,
    "Identifier",
    name,
    {
      name,
    },
    from,
  );
/**
 * Handle literal.
 * @param {*} source Source.
 * @param {*} text Text.
 * @param {*} value Value.
 * @param {number} from From.
 */
const literal = (source, text, value, from = 0) =>
  node(
    source,
    "Literal",
    text,
    {
      value,
    },
    from,
  );
/**
 * Handle block.
 * @param {*} source Source.
 * @param {*} text Text.
 * @param {*} body Body.
 * @param {number} from From.
 */
const block = (source, text, body, from = 0) =>
  node(
    source,
    "BlockStatement",
    text,
    {
      body,
    },
    from,
  );
/**
 * Handle return statement.
 * @param {*} source Source.
 * @param {*} text Text.
 * @param {*} argument Argument.
 * @param {number} from From.
 */
const returnStatement = (source, text, argument, from = 0) =>
  node(
    source,
    "ReturnStatement",
    text,
    {
      argument,
    },
    from,
  );
/**
 * Return scenario.
 * @param {*} source Source.
 * @returns {*} The resulting value.
 * @throws {Error} When the operation cannot complete.
 */
const scenario = source => {
  if (source.includes("SCENARIO_ANALYZE")) {
    const fnText = "function free(x) { return x; }";
    const fn = node(source, "FunctionDeclaration", fnText, {
      id: identifier(source, "free"),
      params: [identifier(source, "x", source.indexOf("free"))],
      async: false,
      generator: false,
    });
    const ret = returnStatement(
      source,
      "return x;",
      identifier(source, "x", source.indexOf("return x")),
    );
    fn.body = block(source, "{ return x; }", [ret]);
    const methodText = "method(y) { return y; }";
    const value = node(source, "FunctionExpression", "(y) { return y; }", {
      id: null,
      params: [identifier(source, "y", source.indexOf("method"))],
      async: false,
      generator: false,
    });
    value.body = block(source, "{ return y; }", [
      returnStatement(
        source,
        "return y;",
        identifier(source, "y", source.indexOf("return y")),
      ),
    ]);
    const method = node(source, "MethodDefinition", methodText, {
      key: identifier(source, "method"),
      value,
      static: false,
      kind: "method",
      computed: false,
    });
    const cls = node(
      source,
      "ClassDeclaration",
      `class Demo { ${methodText} }`,
      {
        id: identifier(source, "Demo"),
        body: {
          type: "ClassBody",
          body: [method],
        },
      },
    );
    const arrowText = "z => z";
    const arrow = node(source, "ArrowFunctionExpression", arrowText, {
      id: null,
      params: [identifier(source, "z", source.indexOf(arrowText))],
      body: identifier(source, "z", source.indexOf("=>") + 2),
      async: false,
      generator: false,
    });
    const decl = {
      type: "VariableDeclarator",
      id: identifier(source, "arrow"),
      init: arrow,
    };
    const variable = node(
      source,
      "VariableDeclaration",
      `const arrow = ${arrowText};`,
      {
        declarations: [decl],
        kind: "const",
      },
    );
    return {
      type: "Program",
      body: [fn, cls, variable],
    };
  }
  if (source.includes("SCENARIO_TO_ARROW")) {
    const fnText = "function double(x) { return x * 2; }";
    const arg = node(source, "BinaryExpression", "x * 2", {
      left: identifier(source, "x", source.indexOf("return")),
      right: literal(source, "2", 2),
      operator: "*",
    });
    const fn = node(source, "FunctionDeclaration", fnText, {
      id: identifier(source, "double"),
      params: [identifier(source, "x", source.indexOf("double"))],
      async: false,
      generator: false,
    });
    fn.body = block(source, "{ return x * 2; }", [
      returnStatement(source, "return x * 2;", arg),
    ]);
    const objectText = "function make(x) { return { value: x }; }";
    const objectArg = node(source, "ObjectExpression", "{ value: x }", {
      properties: [],
    });
    const make = node(source, "FunctionDeclaration", objectText, {
      id: identifier(source, "make"),
      params: [identifier(source, "x", source.indexOf("make"))],
      async: false,
      generator: false,
    });
    make.body = block(source, "{ return { value: x }; }", [
      returnStatement(source, "return { value: x };", objectArg),
    ]);
    const methodSource = "method(a, b) { return a + b; }";
    const mfn = node(source, "FunctionExpression", "(a, b) { return a + b; }", {
      id: null,
      params: [
        identifier(source, "a", source.indexOf(methodSource)),
        identifier(source, "b", source.indexOf(methodSource) + 8),
      ],
      async: false,
      generator: false,
    });
    mfn.body = block(source, "{ return a + b; }", [
      returnStatement(
        source,
        "return a + b;",
        node(source, "BinaryExpression", "a + b", {}),
      ),
    ]);
    const method = node(source, "MethodDefinition", methodSource, {
      key: identifier(source, "method"),
      value: mfn,
      static: false,
      kind: "method",
      computed: false,
    });
    const cls = node(
      source,
      "ClassDeclaration",
      `class Demo { ${methodSource} }`,
      {
        id: identifier(source, "Demo"),
        body: {
          type: "ClassBody",
          body: [method],
        },
      },
    );
    return {
      type: "Program",
      body: [fn, make, cls],
    };
  }
  if (source.includes("SCENARIO_BLOCKERS")) {
    /**
     * Return make method.
     * @param {*} text Text.
     * @param {*} name Name.
     * @param {*} kind Kind.
     * @param {*} semantic Semantic.
     * @returns {*} The resulting value.
     */
    const makeMethod = (text, name, kind, semantic) => {
      const fn = node(source, "FunctionExpression", text.slice(name.length), {
        id: null,
        params: [],
        async: false,
        generator: kind === "generator",
      });
      fn.body = block(
        source,
        text.slice(text.indexOf("{")),
        semantic ? [semantic] : [],
      );
      return node(source, "MethodDefinition", text, {
        key: identifier(source, name),
        value: fn,
        static: false,
        kind: kind === "generator" ? "method" : kind,
        computed: false,
      });
    };
    const thisNode = node(source, "ThisExpression", "this");
    const argNode = identifier(source, "arguments");
    const newNode = node(source, "MetaProperty", "new.target", {
      meta: {
        name: "new",
      },
      property: {
        name: "target",
      },
    });
    const yieldNode = node(source, "YieldExpression", "yield 1", {});
    const methods = [
      makeMethod(
        "constructor() { this.x; }",
        "constructor",
        "constructor",
        thisNode,
      ),
      makeMethod("get value() { arguments; }", "value", "get", argNode),
      makeMethod("set value(v) { new.target; }", "value", "set", newNode),
      makeMethod("gen() { yield 1; }", "gen", "generator", yieldNode),
    ];
    return {
      type: "Program",
      body: [
        {
          type: "ClassDeclaration",
          id: {
            type: "Identifier",
            name: "Demo",
          },
          body: {
            type: "ClassBody",
            body: methods,
          },
        },
      ],
    };
  }
  if (source.includes("SCENARIO_FROM_ARROW")) {
    const arrowText = "x => x + 1";
    const arrow = node(source, "ArrowFunctionExpression", arrowText, {
      params: [identifier(source, "x", source.indexOf(arrowText))],
      body: node(source, "BinaryExpression", "x + 1", {}),
      async: false,
      generator: false,
    });
    const decl = {
      type: "VariableDeclarator",
      id: identifier(source, "inc"),
      init: arrow,
    };
    const variable = node(
      source,
      "VariableDeclaration",
      `const inc = ${arrowText};`,
      {
        declarations: [decl],
        kind: "const",
      },
    );
    const fieldText = "static twice = x => x * 2;";
    const fieldArrow = node(source, "ArrowFunctionExpression", "x => x * 2", {
      params: [identifier(source, "x", source.indexOf(fieldText))],
      body: node(source, "BinaryExpression", "x * 2", {}),
      async: false,
      generator: false,
    });
    const field = node(source, "PropertyDefinition", fieldText, {
      key: identifier(source, "twice"),
      value: fieldArrow,
      static: true,
      computed: false,
    });
    const cls = node(
      source,
      "ClassDeclaration",
      `class Demo { ${fieldText} }`,
      {
        id: identifier(source, "Demo"),
        body: {
          type: "ClassBody",
          body: [field],
        },
      },
    );
    return {
      type: "Program",
      body: [variable, cls],
    };
  }
  if (source.includes("SCENARIO_MISC")) {
    const bodyText = "{ const q = 1; return q; }";
    const fexprText = "function(a) { const q = 1; return q; }";
    const fexpr = node(source, "FunctionExpression", fexprText, {
      id: null,
      params: [identifier(source, "a", source.indexOf(fexprText))],
      async: true,
      generator: false,
    });
    fexpr.body = block(source, bodyText, []);
    const assign = {
      type: "AssignmentExpression",
      left: {
        type: "MemberExpression",
        computed: false,
        property: {
          type: "Identifier",
          name: "work",
        },
      },
      right: fexpr,
    };
    const fieldText = "field = function(v) { return v; };";
    const fieldFn = node(
      source,
      "FunctionExpression",
      "function(v) { return v; }",
      {
        id: null,
        params: [identifier(source, "v", source.indexOf(fieldText))],
        async: false,
        generator: false,
      },
    );
    fieldFn.body = block(source, "{ return v; }", [
      returnStatement(
        source,
        "return v;",
        identifier(source, "v", source.indexOf("return v")),
      ),
    ]);
    const field = node(source, "PropertyDefinition", fieldText, {
      key: identifier(source, "field"),
      value: fieldFn,
      static: false,
      computed: false,
    });
    const staticText = "static ready() { return 1; }";
    const staticFn = node(source, "FunctionExpression", "() { return 1; }", {
      id: null,
      params: [],
      async: false,
      generator: false,
    });
    staticFn.body = block(source, "{ return 1; }", [
      returnStatement(
        source,
        "return 1;",
        literal(source, "1", 1, source.indexOf(staticText)),
      ),
    ]);
    const staticMethod = node(source, "MethodDefinition", staticText, {
      key: identifier(source, "ready"),
      value: staticFn,
      static: true,
      kind: "method",
      computed: false,
    });
    const objectText = "run(x) { return x; }";
    const objectFn = node(source, "FunctionExpression", "(x) { return x; }", {
      id: null,
      params: [identifier(source, "x", source.indexOf(objectText))],
      async: false,
      generator: false,
    });
    objectFn.body = block(source, "{ return x; }", [
      returnStatement(
        source,
        "return x;",
        identifier(source, "x", source.indexOf("return x")),
      ),
    ]);
    const property = node(source, "Property", objectText, {
      key: identifier(source, "run"),
      value: objectFn,
      method: true,
      kind: "init",
      computed: false,
    });
    return {
      type: "Program",
      body: [
        assign,
        {
          type: "ClassDeclaration",
          id: {
            type: "Identifier",
            name: "Misc",
          },
          body: {
            type: "ClassBody",
            body: [field, staticMethod],
          },
        },
        property,
      ],
    };
  }
  if (source.includes("SCENARIO_DEEP_METHODS")) {
    /**
     * Build one fake method definition.
     * @param {string} text Method source text.
     * @param {string} name Method name.
     * @param {Array<*>} bodyNodes Fake body nodes.
     * @param {*} extra Extra method metadata.
     * @returns {*} Fake method node.
     */
    const method = (text, name, bodyNodes, extra = {}) => {
      const fn = node(
        source,
        "FunctionExpression",
        text.slice(text.indexOf("(")),
        {
          id: null,
          params: extra.params ?? [],
          async: extra.async ?? false,
          generator: extra.generator ?? false,
        },
      );
      fn.body = block(source, text.slice(text.indexOf("{")), bodyNodes);
      return node(source, "MethodDefinition", text, {
        key: identifier(source, name, source.indexOf(text)),
        value: fn,
        static: extra.static ?? false,
        kind: extra.kind ?? "method",
        computed: false,
      });
    };
    const nestedRegularText =
      "nestedRegular() { function inner() { return this.x; } return 1; }";
    const nestedRegularFnText = "function inner() { return this.x; }";
    const nestedRegularFn = node(
      source,
      "FunctionDeclaration",
      nestedRegularFnText,
      {
        id: identifier(source, "inner", source.indexOf(nestedRegularFnText)),
        params: [],
        async: false,
        generator: false,
      },
    );
    nestedRegularFn.body = block(source, "{ return this.x; }", [
      node(
        source,
        "ThisExpression",
        "this",
        {},
        source.indexOf(nestedRegularFnText),
      ),
    ]);
    const nestedArrowText =
      "nestedArrow() { const inner = () => this.x; return inner(); }";
    const nestedArrowExpr = "() => this.x";
    const nestedArrow = node(
      source,
      "ArrowFunctionExpression",
      nestedArrowExpr,
      {
        params: [],
        body: node(
          source,
          "ThisExpression",
          "this",
          {},
          source.indexOf(nestedArrowExpr),
        ),
        async: false,
        generator: false,
      },
    );
    const arrowDecl = {
      type: "VariableDeclarator",
      id: identifier(source, "inner", source.indexOf(nestedArrowText)),
      init: nestedArrow,
    };
    const receiverText = "receiver() { return this.x; }";
    const staticText = "static utility(x) { return x; }";
    const plainText = "plain(x) { return x; }";
    const asyncText = "async load(x) { return x; }";
    const getterText = "get value() { return this.x; }";
    const setterText = "set value(v) { this.x = v; }";
    const constructorText = "constructor() { this.x = 1; }";
    const generatorText = "*items() { yield 1; }";
    const methods = [
      method(nestedRegularText, "nestedRegular", [nestedRegularFn]),
      method(nestedArrowText, "nestedArrow", [arrowDecl]),
      method(receiverText, "receiver", [
        node(
          source,
          "ThisExpression",
          "this",
          {},
          source.indexOf(receiverText),
        ),
      ]),
      method(staticText, "utility", [], {
        static: true,
        params: [identifier(source, "x", source.indexOf(staticText))],
      }),
      method(plainText, "plain", [], {
        params: [identifier(source, "x", source.indexOf(plainText))],
      }),
      method(asyncText, "load", [], {
        async: true,
        params: [identifier(source, "x", source.indexOf(asyncText))],
      }),
      method(
        getterText,
        "value",
        [
          node(
            source,
            "ThisExpression",
            "this",
            {},
            source.indexOf(getterText),
          ),
        ],
        {
          kind: "get",
        },
      ),
      method(
        setterText,
        "value",
        [
          node(
            source,
            "ThisExpression",
            "this",
            {},
            source.indexOf(setterText),
          ),
        ],
        {
          kind: "set",
          params: [identifier(source, "v", source.indexOf(setterText))],
        },
      ),
      method(
        constructorText,
        "constructor",
        [
          node(
            source,
            "ThisExpression",
            "this",
            {},
            source.indexOf(constructorText),
          ),
        ],
        {
          kind: "constructor",
        },
      ),
      method(
        generatorText,
        "items",
        [node(source, "YieldExpression", "yield 1", {})],
        {
          generator: true,
        },
      ),
    ];
    return {
      type: "Program",
      body: [
        {
          type: "ClassDeclaration",
          id: {
            type: "Identifier",
            name: "Deep",
          },
          body: {
            type: "ClassBody",
            body: methods,
          },
        },
      ],
    };
  }
  if (source.includes("SCENARIO_PARAMETERS")) {
    /** @type {Array<[string, string, Array<*>]>} */
    const texts = [
      [
        "one(x) { return x; }",
        "one",
        [identifier(source, "x", source.indexOf("one(x)"))],
      ],
      [
        "many(a, b) { return a; }",
        "many",
        [
          identifier(source, "a", source.indexOf("many(a")),
          identifier(source, "b", source.indexOf("many(a") + 3),
        ],
      ],
      ["none() { return 1; }", "none", []],
    ];
    const methods = texts.map(([text, name, params]) => {
      const fn = node(
        source,
        "FunctionExpression",
        text.slice(text.indexOf("(")),
        {
          id: null,
          params,
          async: false,
          generator: false,
        },
      );
      fn.body = block(source, text.slice(text.indexOf("{")), []);
      return node(source, "MethodDefinition", text, {
        key: identifier(source, name, source.indexOf(text)),
        value: fn,
        static: false,
        kind: "method",
        computed: false,
      });
    });
    return {
      type: "Program",
      body: [
        {
          type: "ClassDeclaration",
          id: {
            type: "Identifier",
            name: "Params",
          },
          body: {
            type: "ClassBody",
            body: methods,
          },
        },
      ],
    };
  }
  if (source.includes("SCENARIO_ARROW_BLOCKED")) {
    const arrowText = "x => this.x";
    const arrow = node(source, "ArrowFunctionExpression", arrowText, {
      params: [identifier(source, "x", source.indexOf(arrowText))],
      body: node(source, "ThisExpression", "this"),
      async: false,
      generator: false,
    });
    return {
      type: "Program",
      body: [
        {
          type: "VariableDeclarator",
          id: identifier(source, "blocked"),
          init: arrow,
        },
      ],
    };
  }
  if (source.includes("SCENARIO_METHOD_FRINGE")) {
    /**
     * Build one fake method definition.
     * @param {string} text Method source text.
     * @param {string} name Method name.
     * @param {Array<*>} semantic Fake body nodes.
     * @param {*} extra Extra method metadata.
     * @returns {*} Fake method node.
     */
    const method = (text, name, semantic = [], extra = {}) => {
      const fn = node(
        source,
        "FunctionExpression",
        text.slice(text.indexOf("(")),
        {
          id: null,
          params: extra.params ?? [],
          async: false,
          generator: extra.generator ?? false,
        },
      );
      fn.body = block(source, text.slice(text.indexOf("{")), semantic);
      return node(source, "MethodDefinition", text, {
        key: identifier(source, name, source.indexOf(text)),
        value: fn,
        static: extra.static ?? false,
        kind: extra.kind ?? "method",
        computed: false,
      });
    };
    const argsText = "argsOnly() { return arguments.length; }";
    const targetText = "targetOnly() { return new.target; }";
    const genText = "*gen() { yield 1; }";
    const ctorText = "constructor() { return 1; }";
    const getText = "get value() { return 1; }";
    const setText = "set value(v) { cache = v; }";
    const plainText = "plain() { return 1; }";
    const methods = [
      method(argsText, "argsOnly", [
        identifier(source, "arguments", source.indexOf(argsText)),
      ]),
      method(targetText, "targetOnly", [
        node(
          source,
          "MetaProperty",
          "new.target",
          {
            meta: {
              name: "new",
            },
            property: {
              name: "target",
            },
          },
          source.indexOf(targetText),
        ),
      ]),
      method(
        genText,
        "gen",
        [
          node(
            source,
            "YieldExpression",
            "yield 1",
            {},
            source.indexOf(genText),
          ),
        ],
        {
          generator: true,
        },
      ),
      method(ctorText, "constructor", [], {
        kind: "constructor",
      }),
      method(getText, "value", [], {
        kind: "get",
      }),
      method(setText, "value", [], {
        kind: "set",
        params: [identifier(source, "v", source.indexOf(setText))],
      }),
      method(plainText, "plain"),
    ];
    return {
      type: "Program",
      body: [
        {
          type: "ClassDeclaration",
          id: {
            type: "Identifier",
            name: "Fringe",
          },
          body: {
            type: "ClassBody",
            body: methods,
          },
        },
      ],
    };
  }
  if (source.includes("SCENARIO_IDENTITY_FRINGE")) {
    /**
     * Build one fake function declaration.
     * @param {string} text Declaration source text.
     * @param {string} name Function name.
     * @param {Array<*>} semantic Fake body nodes.
     * @returns {*} Fake declaration node.
     */
    const makeDeclaration = (text, name, semantic = []) => {
      const fn = node(source, "FunctionDeclaration", text, {
        id: identifier(source, name, source.indexOf(text)),
        params: [],
        async: false,
        generator: name === "gen",
      });
      fn.body = block(source, text.slice(text.indexOf("{")), semantic);
      return fn;
    };
    const hoistedText = "function hoisted() { return 1; }";
    const ctorText = "function Ctor() { return 1; }";
    const protoText = "function Proto() { return 1; }";
    const safeText = "function safe() { return 1; }";
    const argsText = "function argsOnly() { return arguments.length; }";
    const targetText = "function targetOnly() { return new.target; }";
    const genText = "function* gen() { yield 1; }";
    const hoisted = makeDeclaration(hoistedText, "hoisted");
    const ctor = makeDeclaration(ctorText, "Ctor");
    const proto = makeDeclaration(protoText, "Proto");
    const safe = makeDeclaration(safeText, "safe", [
      returnStatement(
        source,
        "return 1;",
        literal(source, "1", 1, source.indexOf(safeText)),
        source.indexOf(safeText),
      ),
    ]);
    const argsOnly = makeDeclaration(argsText, "argsOnly", [
      identifier(source, "arguments", source.indexOf(argsText)),
    ]);
    const targetOnly = makeDeclaration(targetText, "targetOnly", [
      node(
        source,
        "MetaProperty",
        "new.target",
        {
          meta: {
            name: "new",
          },
          property: {
            name: "target",
          },
        },
        source.indexOf(targetText),
      ),
    ]);
    const gen = makeDeclaration(genText, "gen", [
      node(source, "YieldExpression", "yield 1", {}, source.indexOf(genText)),
    ]);
    const before = node(source, "CallExpression", "hoisted()", {
      callee: identifier(source, "hoisted"),
      arguments: [],
    });
    const construct = node(source, "NewExpression", "new Ctor()", {
      callee: identifier(source, "Ctor", source.indexOf("new Ctor")),
      arguments: [],
    });
    const prototype = node(source, "MemberExpression", "Proto.prototype", {
      object: identifier(source, "Proto", source.indexOf("Proto.prototype")),
      property: identifier(
        source,
        "prototype",
        source.indexOf("Proto.prototype"),
      ),
      computed: false,
    });
    const namedText = "function recur() { return 1; }";
    const named = node(source, "FunctionExpression", namedText, {
      id: identifier(source, "recur", source.indexOf(namedText)),
      params: [],
      async: false,
      generator: false,
    });
    named.body = block(source, "{ return 1; }", [], source.indexOf(namedText));
    const namedDecl = {
      type: "VariableDeclarator",
      id: identifier(source, "named"),
      init: named,
    };
    return {
      type: "Program",
      body: [
        before,
        hoisted,
        ctor,
        construct,
        proto,
        prototype,
        safe,
        argsOnly,
        targetOnly,
        gen,
        namedDecl,
      ],
    };
  }
  if (source.includes("SCENARIO_LEXICAL_ARROWS")) {
    /**
     * Build one fake arrow declarator.
     * @param {string} text Arrow source text.
     * @param {string} name Declared name.
     * @param {*} semantic Fake arrow body node.
     * @returns {*} Fake declarator node.
     */
    const makeArrow = (text, name, semantic) => {
      const arrow = node(source, "ArrowFunctionExpression", text, {
        params: [],
        body: semantic,
        async: false,
        generator: false,
      });
      return {
        type: "VariableDeclarator",
        id: identifier(source, name),
        init: arrow,
      };
    };
    const thisArrow = makeArrow(
      "() => this.x",
      "lexicalThis",
      node(source, "ThisExpression", "this"),
    );
    const argsArrow = makeArrow(
      "() => arguments[0]",
      "lexicalArgs",
      identifier(source, "arguments", source.indexOf("arguments")),
    );
    const targetArrow = makeArrow(
      "() => new.target",
      "lexicalTarget",
      node(source, "MetaProperty", "new.target", {
        meta: {
          name: "new",
        },
        property: {
          name: "target",
        },
      }),
    );
    const safeArrow = makeArrow(
      "() => 1",
      "safeArrow",
      literal(source, "1", 1, source.lastIndexOf("1")),
    );
    return {
      type: "Program",
      body: [thisArrow, argsArrow, targetArrow, safeArrow],
    };
  }
  if (source.includes("SCENARIO_PARSE_FAIL")) throw new Error("script failure");
  if (source.includes("SCENARIO_SCRIPT_FALLBACK"))
    return {
      type: "Program",
      body: [],
    };
  throw new Error("Unknown fixture scenario");
};
/**
 * Parse one fixture source.
 * @param {*} source Source text.
 * @param {*} options Parser options.
 * @returns {*} Fixture AST.
 */
exports.parse = (source, options) => {
  if (
    source.includes("SCENARIO_SCRIPT_FALLBACK") &&
    options.sourceType === "module"
  )
    throw new Error("module failure");
  return scenario(source);
};
