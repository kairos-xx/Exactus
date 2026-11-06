/** Read JavaScript/TypeScript/CSS syntax without executing submitted source. */
"use strict";
/* global require, process */
const fs = require("node:fs");
const path = require("node:path");
const childProcess = require("node:child_process");
/**
 * Load a parser package, falling back to the global npm root.
 * @param {string} name Package name to require.
 * @returns {any} Loaded module.
 */
const load = name => {
  try {
    return require(name);
  } catch (error) {
    if (/** @type {any} */ (error) && /** @type {any} */ (error).code !== "MODULE_NOT_FOUND") throw error;
    return require(
      path.join(
        childProcess
          .execFileSync("npm", ["root", "-g"], {encoding: "utf8"})
          .trim(),
        name
      )
    );
  }
};
/** Parse one snapshot, returning a JSON-serializable response without emitting partial output.
 * @param {Record<string, unknown>} request
 * @returns {Record<string, unknown>}
 */
const parseRequest = request => {
  /** @type {string} */
  const source = /** @type {string} */ (Reflect.get(request, "source"));
  /** @type {string} */
  const language = /** @type {string} */ (Reflect.get(request, "language"));
  /** @type {Record<string, unknown>} */
  let result = {
    valid: false,
    error: "Parser produced no result",
    units: [],
    statements: []
  };
  /**
   * Record a parse result for the batch response.
   * @param {Record<string, unknown>} value Result payload.
   * @returns {void}
   */
  const output = value => {
    result = value;
  };
  if (language === "javascript" || language === "typescript") {
    const ts = load("typescript");
    if (Reflect.get(request, "action") === "rewrite_identifiers") {
      const prefix = "function __mergekit__() {\n";
      const wrapped = `${prefix + source}\n}`;
      const document = ts.createSourceFile(
        "rewrite.ts",
        wrapped,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TS
      );
      if (document.parseDiagnostics.length) {
        output({
          valid: false,
          error:
            "Cannot parse inserted JS statement for bound-identifier rewriting"
        });
        return result;
      }
      /** @type {Record<string, string>} */
      const mapping = /** @type {Record<string, string>} */ (Reflect.get(request, "mapping"));
      /** @type {{start: number, end: number, replacement: string}[]} */
      const mutations = [];
      /** @type {string} */
      let ambiguous = "";
      /**
       * Visit each AST node, renaming safe identifier references.
       * @param {any} node TypeScript AST node.
       * @returns {void}
       */
      const visit = node => {
        if (ts.isIdentifier(node) && Object.hasOwn(mapping, node.text)) {
          const parent = node.parent;
          if (ts.isPropertyAccessExpression(parent) && parent.name === node)
            return;
          if (
            (ts.isPropertyAssignment(parent) ||
              ts.isMethodDeclaration(parent)) &&
            parent.name === node
          )
            return;
          if (
            ts.isShorthandPropertyAssignment(parent) ||
            (ts.isVariableDeclaration(parent) && parent.name === node) ||
            (ts.isParameter(parent) && parent.name === node) ||
            (ts.isFunctionDeclaration(parent) && parent.name === node)
          ) {
            ambiguous =
              "Renaming an identifier declaration or shorthand property requires scope analysis";
            return;
          }
          const start = node.getStart(document) - prefix.length;
          const end = node.getEnd() - prefix.length;
          if (start >= 0 && end <= source.length)
            mutations.push({start, end, replacement: mapping[node.text] || ""});
        }
        ts.forEachChild(node, visit);
      };
      visit(document);
      if (ambiguous) output({valid: false, error: ambiguous});
      else {
        let rewritten = source;
        for (const edit of mutations.sort((a, b) => b.start - a.start))
          rewritten =
            rewritten.slice(0, edit.start) +
            edit.replacement +
            rewritten.slice(edit.end);
        output({valid: true, text: rewritten});
      }
      return result;
    }
    const file = ts.createSourceFile(
      `input.${language === "typescript" ? "ts" : "js"}`,
      source,
      ts.ScriptTarget.Latest,
      true,
      language === "typescript" ? ts.ScriptKind.TS : ts.ScriptKind.JS
    );
    if (file.parseDiagnostics.length) {
      output({
        valid: false,
        error: file.parseDiagnostics
          .map(/** @param {any} d */ d => ts.flattenDiagnosticMessageText(d.messageText, " "))
          .join("; "),
        units: [],
        statements: []
      });
      return result;
    }
    /**
     * Compute a name-insensitive structural fingerprint.
     * @param {any} node TypeScript AST node.
     * @returns {string} Normalized subtree shape.
     */
    const shape = node => {
      if (ts.isIdentifier(node)) return "id";
      if (ts.isStringLiteral(node) || ts.isNumericLiteral(node))
        return `${ts.SyntaxKind[node.kind]}:${node.text}`;
      if (ts.isTypeNode(node)) return "type";
      if (ts.isVariableDeclarationList(node))
        return `VariableDeclarationList:${node.flags}(${node.declarations.map(shape).join(",")})`;
      if (ts.isPropertyAccessExpression(node))
        return `attr(${shape(node.expression)},${node.name ? "field" : ""})`;
      /** @type {string[]} */
      const children = [];
      ts.forEachChild(node, /** @param {any} child */ child => {
        if (!ts.isTypeNode(child) && !ts.isModifier(child))
          children.push(shape(child));
      });
      return `${ts.SyntaxKind[node.kind]}(${children.join(",")})`;
    };
    /**
     * Compute a name-aware semantic fingerprint.
     * @param {any} node TypeScript AST node.
     * @returns {string} Identifier-preserving subtree shape.
     */
    const exact = node => {
      if (ts.isIdentifier(node)) return `id:${node.text}`;
      if (ts.isStringLiteral(node) || ts.isNumericLiteral(node))
        return `${ts.SyntaxKind[node.kind]}:${node.text}`;
      if (ts.isTypeNode(node)) return "type";
      if (ts.isVariableDeclarationList(node))
        return `VariableDeclarationList:${node.flags}(${node.declarations.map(exact).join(",")})`;
      /** @type {string[]} */
      const children = [];
      ts.forEachChild(node, /** @param {any} child */ child => {
        if (!ts.isTypeNode(child) && !ts.isModifier(child))
          children.push(exact(child));
      });
      return `${ts.SyntaxKind[node.kind]}(${children.join(",")})`;
    };
    /**
     * Build a statement wire record from an AST node.
     * @param {any} node TypeScript AST node.
     * @returns {any} Statement record with spans and fingerprints.
     */
    const stmt = node => ({
      kind: ts.SyntaxKind[node.kind],
      start: node.getStart(file),
      end: node.end,
      shape: shape(node),
      exact: exact(node),
      binding:
        ts.isVariableStatement(node) &&
        node.declarationList.declarations.length === 1 &&
        ts.isIdentifier(node.declarationList.declarations[0].name)
          ? node.declarationList.declarations[0].name.text
          : "",
      annotation:
        ts.isVariableStatement(node) &&
        node.declarationList.declarations.length === 1 &&
        node.declarationList.declarations[0].type
          ? node.declarationList.declarations[0].type.getText(file)
          : ""
    });
    /** @type {any[]} */
    const units = [];
    /** @type {any[]} */
    const statements = [];
    /**
     * Walk the AST collecting declarations and statements.
     * @param {any} node TypeScript AST node.
     * @param {string} owner Enclosing declaration name.
     * @returns {void}
     */
    const walk = (node, owner) => {
      const declaration = node;
      /** @type {any} */
      let fn = null;
      /** @type {string} */
      let name = "";
      /** @type {string} */
      let parent = owner;
      if (
        ts.isFunctionDeclaration(node) ||
        ts.isMethodDeclaration(node) ||
        ts.isConstructorDeclaration(node)
      ) {
        fn = node;
        name = node.name ? node.name.getText(file) : "constructor";
      } else if (
        ts.isVariableStatement(node) &&
        node.declarationList.declarations.length === 1
      ) {
        const decl = node.declarationList.declarations[0];
        if (
          decl.initializer &&
          (ts.isArrowFunction(decl.initializer) ||
            ts.isFunctionExpression(decl.initializer))
        ) {
          fn = decl.initializer;
          name = decl.name.getText(file);
        }
      } else if (
        ts.isPropertyDeclaration(node) &&
        node.initializer &&
        ts.isArrowFunction(node.initializer)
      ) {
        fn = node.initializer;
        name = node.name.getText(file);
      }
      if (fn && fn.body && name) {
        const body = fn.body;
        const implicit = !ts.isBlock(body);
        const children = implicit
          ? [
              {
                kind: "ReturnStatement",
                start: body.getStart(file),
                end: body.end,
                shape: `ReturnStatement(${shape(body)})`,
                exact: `ReturnStatement(${exact(body)})`,
                binding: ""
              }
            ]
          : body.statements.map(stmt);
        const parameters = fn.parameters.map(/** @param {any} p */ p => p.name.getText(file));
        const unit = {
          kind: implicit ? "arrow" : "function",
          name,
          parent,
          start: declaration.getStart(file),
          end: declaration.end,
          body_start: implicit ? body.getStart(file) : body.getStart(file) + 1,
          body_end: implicit ? body.end : body.end - 1,
          statements: children,
          fingerprint: children.map(/** @param {{shape: string}} x */ x => x.shape).join("|"),
          signature: `arity:${parameters.length}`,
          param_names: parameters,
          implicit_return: implicit,
          header_semantic: JSON.stringify({
            parameters,
            modifiers: (declaration.modifiers || fn.modifiers || []).map(
              /** @param {any} m */ m => m.kind
            ),
            generator: Boolean(fn.asteriskToken),
            defaults: fn.parameters.map(/** @param {any} p */ p =>
              p.initializer ? shape(p.initializer) : ""
            )
          })
        };
        units.push(unit);
        statements.push(...children);
        for (const child of /** @type {any[]} */ (fn.body.statements || []))
          walk(child, parent + (parent ? "." : "") + name);
        return;
      }
      if (ts.isClassDeclaration(node) && node.name)
        parent = owner + (owner ? "." : "") + node.name.text;
      ts.forEachChild(node, /** @param {any} child */ child => walk(child, parent));
    };
    walk(file, "");
    output({valid: true, units, statements});
  } else if (language === "css") {
    const postcss = load("postcss");
    try {
      const root = postcss.parse(source, /** @type {any} */ ({from: undefined}));
      /** @type {any[]} */
      const units = [];
      /** @type {any[]} */
      const statements = [];
      /**
       * Walk the CSS AST collecting rules and declarations.
       * @param {any} node PostCSS AST node.
       * @param {string} parent Enclosing selector or rule name.
       * @returns {void}
       */
      const walk = (node, parent) => {
        if (
          node.type === "rule" &&
          node.source &&
          node.source.start &&
          node.source.end
        ) {
          const start = /** @type {number} */ (node.source.start.offset ?? 0);
          let end = Math.min(source.length, /** @type {number} */ (node.source.end.offset ?? 0) + 1);
          while (end > start && /\s/.test(source.charAt(end - 1))) end--;
          const opening = source.indexOf("{", start);
          const children = node.nodes
            .filter(/** @param {any} item */ item => item.type === "decl")
            .map(/** @param {any} item */ item => {
              const begin = /** @type {number} */ (item.source.start.offset ?? 0);
              let finish = Math.min(source.length, /** @type {number} */ (item.source.end.offset ?? 0) + 1);
              while (finish > begin && /\s/.test(source.charAt(finish - 1))) finish--;
              const colon = source.indexOf(":", begin);
              const segment = source.slice(colon + 1, finish);
              const valueStart =
                colon + 1 + (segment.length - segment.trimStart().length);
              const valueEnd = finish - (segment.endsWith(";") ? 1 : 0);
              return {
                kind: "declaration",
                start: begin,
                end: finish,
                shape: `decl:${item.value}:${Boolean(item.important)}`,
                exact: `${item.prop}:${item.value}:${Boolean(item.important)}`,
                binding: item.prop,
                value_start: valueStart,
                value_end: valueEnd
              };
            });
          units.push({
            kind: "rule",
            name: node.selector,
            parent,
            start,
            end,
            body_start: opening + 1,
            body_end: end - 1,
            statements: children,
            fingerprint: children.map(/** @param {{shape: string}} item */ item => item.shape).join("|"),
            signature: "rule",
            param_names: []
          });
          statements.push(...children);
        }
        if (node.nodes)
          for (const child of /** @type {any[]} */ (node.nodes))
            walk(
              /** @type {any} */ (child),
              node.type === "atrule"
                ? `${parent}@${node.name}(${node.params})`
                : parent
            );
      };
      walk(root, "");
      output({valid: true, units, statements});
    } catch (error) {
      output({valid: false, error: String(/** @type {any} */ (error)), units: [], statements: []});
    }
  } else
    output({
      valid: false,
      error: `Unsupported language: ${language}`,
      units: [],
      statements: []
    });
  return result;
};
/** @type {{batch?: {source?: string, language?: string, mapping?: Record<string, string>, action?: string}[], source?: string, language?: string, mapping?: Record<string, string>, action?: string}} */
const request = JSON.parse(fs.readFileSync(0, "utf8"));
const response = Array.isArray(request.batch)
  ? request.batch.map(parseRequest)
  : parseRequest(request);
process.stdout.write(JSON.stringify(response));
