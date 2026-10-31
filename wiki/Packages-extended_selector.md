[Home](Home.md) > [Packages](Packages.md) > extended_selector

# ExtendedSelector — Complete Technical Documentation

The selector **engine** and its structured formula editor. The expression widget that edits selectors in Studio lives in its own package, [`widget_selector/`](Packages-widgets-widget_selector.md).

## 1. Overview

`ExtendedSelector` is a browser-native, dependency-free DOM and visual query engine that extends ordinary CSS selection with predicates, boolean algebra, structural relations, geometry, viewport state, scrolling, stacking order, Shadow DOM, slots, pseudo-element style inspection, extensibility hooks, diagnostics, compilation, and a structured formula-style frontend editor.

The system consists of two independent layers:

1. **`extended-selector.js`** — the query/parser/evaluation engine.
2. **`extended-selector-editor.js` + `extended-selector-editor.css`** — an optional formula-style visual expression editor.

The engine is synchronous and designed for current-document DOM querying. The editor serializes its structured pill tree into the exact expression language consumed by the engine.

---

## 2. Files

| File | Purpose |
|---|---|
| `extended-selector.js` | Core parser, linter and query engine. |
| `extended-selector-editor.js` | Formula-style nested-pill expression editor. |
| `extended-selector-editor.css` | Editor presentation and nesting styles. |
| `demo.html` | Browser demonstration and integration example. |
| `verify.mjs` | Node verification harness: cross-checks `ExtendedSelector`/`bestLocalSelector` output against `css-selector-generator`, `optimal-select` and `@medv/finder` for selector parity. |
| `DOC.md` | This complete reference. |

---

## 3. Installation

No package installation is required. Use the files as ES modules:

```js
import ExtendedSelector from "./extended-selector.js";
import ExtendedSelectorEditor from "./extended-selector-editor.js";
```

Load the editor stylesheet when the visual editor is used:

```html
<link rel="stylesheet" href="./extended-selector-editor.css">
```

Create an engine:

```js
const engine = new ExtendedSelector(document);
```

A subtree can be used instead:

```js
const root = document.querySelector("#application");
const engine = new ExtendedSelector(root);
```

---

## 4. Design principles

The language deliberately combines native CSS with higher-level predicates and relational operators.

A plain CSS selector remains valid:

```text
.card > button.save
```

An extended predicate can be attached to a CSS atom:

```text
button[innerText="Save *"]
```

Functions compose expressions:

```text
has(.card, button[innerText="Save *"])
```

Expressions can be arbitrarily nested:

```text
and(
    .card[visible=true],
    has(
        .card,
        button[innerText="Save *"]
    )
)
```

The core is:

- browser-native;
- dependency-free;
- synchronous;
- deterministic for a fixed DOM/layout state;
- compositional;
- extensible through predicates and operators;
- compatible with ordinary CSS atoms;
- usable without the frontend editor.

---

# 5. Quick start

Given:

```html
<article class="card">
    <h2 class="title">Order 1042</h2>
    <button>Save order</button>
</article>
```

Query by text:

```js
const button = engine.queryOne('button[innerText="Save *"]');
```

Query structurally:

```js
const card = engine.queryOne(`
    children(
        .card,
        .title[textContent="Order *"],
        button[innerText="Save *"]
    )
`);
```

Boolean composition:

```js
const matches = engine.query(`
    and(
        .card[visible=true],
        has(.card, button[innerText="Save *"])
    )
`);
```

---

# 6. Core API

## 6.1 Constructor

```js
new ExtendedSelector(root?, options?)
```

### `root`

`Document | Element`

Default:

```js
document
```

The root determines the default query universe.

### `options`

```js
{
    strict?: boolean,
    deduplicate?: boolean,
    sortDocumentOrder?: boolean
}
```

Defaults:

```js
{
    strict: true,
    deduplicate: true,
    sortDocumentOrder: true
}
```

`deduplicate` removes duplicate elements from final results.

`sortDocumentOrder` sorts final results into document order.

`strict` is part of the public configuration surface, but the current implementation does not yet use it to change parsing/evaluation behavior.

---

## 6.2 `configure()`

```js
engine.configure(options)
```

Merges new options and returns the engine.

```js
engine.configure({
    deduplicate: false
});
```

---

## 6.3 `setRoot()`

```js
engine.setRoot(root)
```

Changes the default query root.

```js
engine.setRoot(document.querySelector(".workspace"));
```

Returns `this`.

---

## 6.4 `universe()`

```js
engine.universe(root?)
```

Returns all elements in the query universe.

For an `Element` root, the root itself is included.

For a `Document`, descendant elements are returned.

```js
const elements = engine.universe();
```

---

## 6.5 `query()`

```js
engine.query(expression, options?)
```

Returns every matching element.

```js
const buttons = engine.query('button[visible=true]');
```

`expression` may be source text or an already parsed AST.

Per-query options:

```js
engine.query(expression, {
    root: someElement,
    universe: explicitElements
});
```

When `universe` is supplied, it takes precedence over `root`.

A successful query dispatches a `query` event containing:

```js
{
    expression,
    ast,
    elements,
    count,
    duration
}
```

Example:

```js
engine.addEventListener("query", ({detail}) => {
    console.log(detail.count, detail.duration);
});
```

---

## 6.6 `queryOne()`

```js
engine.queryOne(expression, options?)
```

Returns the first match or `null`.

```js
const save = engine.queryOne('button[innerText="Save *"]');
```

---

## 6.7 `count()`

```js
engine.count(expression, options?)
```

Returns the number of matches.

```js
const visibleCards = engine.count(".card[visible=true]");
```

This API method must not be confused with an expression-language `count(...)` operator. The current expression evaluator intentionally does **not** provide a usable `count(...)` operator.

---

## 6.8 `exists()`

```js
engine.exists(expression, options?)
```

Returns whether at least one match exists.

```js
if (engine.exists(".modal[visible=true]")) {
    // ...
}
```

---

## 6.9 `matches()`

```js
engine.matches(element, expression)
```

Tests one element.

```js
engine.matches(button, 'button[innerText="Save *"]');
```

### Important relational limitation

`matches()` evaluates against `[element]` as its universe. Expressions requiring other elements from the root may therefore behave differently from a normal root query.

For relational expressions, prefer:

```js
engine.query(expression).includes(element)
```

when root-wide reference resolution is required.

---

## 6.10 `filter()`

```js
engine.filter(elements, expression)
```

Filters an iterable of elements.

```js
const visible = engine.filter(nodes, "[visible=true]");
```

As with `matches()`, relational expressions operate against the supplied element universe.

---

# 7. Parsing

## 7.1 `parse()`

```js
engine.parse(expression)
```

Runs linting and then parses the expression.

Returns an AST.

Throws `SyntaxError` when lint diagnostics exist.

---

## 7.2 AST format

Atoms:

```js
{
    type: "atom",
    value: ".card[visible=true]"
}
```

Calls:

```js
{
    type: "call",
    name: "has",
    args: [...],
    rawArgs: [...]
}
```

Example:

```text
has(.card, button)
```

approximately becomes:

```js
{
    type: "call",
    name: "has",
    args: [
        {type: "atom", value: ".card"},
        {type: "atom", value: "button"}
    ],
    rawArgs: [
        ".card",
        "button"
    ]
}
```

`rawArgs` exists because some operators require raw tokens rather than evaluated expressions.

---

## 7.3 `parseExtended()`

```js
engine.parseExtended(expression)
```

Parses without linting.

This is a lower-level API. Normal consumers should prefer `parse()`.

The parser recognizes:

```text
operator(arg1, arg2, ...)
```

and unary shorthand:

```text
!(expression)
```

The shorthand is represented as `not(expression)`.

---

## 7.4 `splitTopLevel()`

```js
ExtendedSelector.splitTopLevel(value, delimiter?)
```

Splits only at top-level delimiters, ignoring commas nested inside:

- `(...)`;
- `[...]`;
- quoted strings.

Example:

```js
ExtendedSelector.splitTopLevel(
    '.a, has(.b, .c), [textContent="a,b"]'
);
```

produces three top-level components.

---

# 8. Validation and diagnostics

## 8.1 `lint()`

```js
engine.lint(expression)
```

Never intentionally throws for ordinary invalid source.

Returns:

```js
SelectorDiagnostic[]
```

A diagnostic has:

```js
{
    code,
    message,
    offset,
    line,
    column,
    length,
    lineText,
    pointer
}
```

Example:

```js
const diagnostics = engine.lint("and(.a)");

diagnostics.forEach((diagnostic) => {
    console.log(engine.formatDiagnostic(diagnostic));
});
```

---

## 8.2 Diagnostic codes

Current diagnostics include:

- `type`
- `empty`
- `unexpected-close`
- `unterminated-string`
- `unclosed-delimiter`
- `invalid-css`
- `unknown-operator`
- `arity`
- `parse`

---

## 8.3 `formatDiagnostic()`

```js
engine.formatDiagnostic(diagnostic)
```

Produces human-readable output such as:

```text
arity: and() expects 2–∞ arguments; received 1. (1:1)
and(.card)
^^^
```

---

## 8.4 `validate()`

```js
engine.validate(expression)
```

Returns:

```js
{
    valid,
    ast,
    error,
    diagnostics
}
```

Example:

```js
const result = engine.validate(source);

if (!result.valid)
    console.error(result.diagnostics);
```

---

## 8.5 `position()`

```js
ExtendedSelector.position(expression, offset)
```

Converts a character offset into:

```js
{
    offset,
    line,
    column
}
```

---

## 8.6 `diagnostic()`

Low-level diagnostic factory:

```js
ExtendedSelector.diagnostic(
    expression,
    message,
    offset,
    length,
    code
);
```

---

## 8.7 `syntaxError()`

Creates a `SyntaxError` with an attached diagnostic:

```js
const error = ExtendedSelector.syntaxError(
    expression,
    "Unexpected token.",
    offset
);
```

---

# 9. Compilation

## 9.1 `compile()`

```js
const query = engine.compile(expression);
```

The expression is parsed once.

Then:

```js
const first = query();
const second = query({root: anotherRoot});
```

The returned function exposes:

```js
query.ast
query.expression
```

Compilation avoids reparsing the source on subsequent calls.

It does not precompute DOM/layout results.

---

# 10. Explanation

```js
engine.explain(expression, options?)
```

Returns:

```js
{
    expression,
    ast,
    count,
    elements,
    summary
}
```

Example:

```js
const explanation = engine.explain(".card[visible=true]");
```

The current explanation API summarizes the final query. It is **not yet** a predicate-by-predicate proof tree.

---

# 11. CSS atoms

Every expression leaf is fundamentally a CSS atom plus optional extended predicates.

Examples:

```text
button
```

```text
.card
```

```text
#save
```

```text
main > article.card
```

```text
button.action.primary
```

Native CSS matching is performed with `Element.matches()`.

---

# 12. Extended predicates

Extended predicates use CSS-attribute-like syntax:

```text
[key=value]
```

Supported comparison operators:

```text
=
!=
<
<=
>
>=
~=
```

Examples:

```text
button[visible=true]
```

```text
.card[width>300px]
```

```text
.title[textContent="Order *"]
```

Multiple predicates may be attached to an atom.

---

# 13. Wildcards

For `=` and `!=`, `*` acts as a wildcard.

```text
[textContent="Order *"]
```

matches text beginning with `Order ` and followed by any text.

```text
[innerText!="Error *"]
```

negates a wildcard match.

Wildcard matching is anchored to the complete value.

---

# 14. Numeric comparisons

When both actual and expected values can be parsed numerically, numeric comparison is used.

Examples:

```text
[width>300px]
[children>=2]
[viewport_ratio>0.5]
```

### Unit caveat

The generic comparator currently uses `parseFloat()` for numeric comparison. It is **not** a complete dimensional/unit conversion system.

For example, arbitrary comparison between:

```text
1rem
```

and:

```text
16px
```

does not imply browser-aware conversion.

---

# 15. Color similarity

`~=` is currently the color-similarity operator.

Syntax:

```text
[color~=rgb(200,0,0),1]
```

Similarity `1` means exact RGB equality.

Lower thresholds allow increasing distance:

```text
[color~=rgb(200,0,0),0.95]
```

The comparison uses normalized Euclidean RGB channel distance.

Alpha is not part of the similarity distance.

---

# 16. Built-in predicate values

## 16.1 Text and content

```text
[textContent="..."]
[innerText="..."]
[innerHTML="..."]
[normalizedText="..."]
[value="..."]
```

`normalizedText` collapses whitespace and trims the result.

---

## 16.2 Accessibility-related values

```text
[role="button"]
[accessible_name="Save"]
```

`role` uses an explicit role when present and a small built-in implicit-role approximation for common elements.

`accessible_name` uses an approximation based on:

- `aria-label`;
- `aria-labelledby`;
- `alt`;
- `title`;
- visible inner text.

This is **not** a complete implementation of the W3C accessible-name algorithm.

---

## 16.3 Visibility and state

```text
[visible=true]
[rendered=true]
[enabled=true]
[disabled=true]
[focused=true]
[checked=true]
[selected=true]
[editable=true]
[clickable=true]
[draggable=true]
[scrollable=true]
```

### Visibility caveat

`visible` is a practical heuristic based on:

- `display`;
- `visibility`;
- opacity;
- non-zero bounding rectangle.

It does not fully model clipping, occlusion, paint containment, or every browser rendering edge case.

`clickable` is also heuristic.

---

## 16.4 Viewport state

```text
[in_viewport=true]
[viewport_ratio>0.5]
[above_viewport=true]
[below_viewport=true]
```

`viewport_ratio` is the fraction of the element's rectangle intersecting the viewport.

---

## 16.5 Geometry

```text
[width>100px]
[height>=40px]
[area>10000]
[aspect_ratio>1]
[x_abs>100px]
[y_abs>100px]
[right_abs<1200px]
[bottom_abs<900px]
[center_x_abs>500px]
[center_y_abs>300px]
[x_view>20px]
[y_view>20px]
[distance_to_viewport_top<50px]
```

`area` is currently returned with a `px` suffix even though the physical dimension is conceptually square pixels.

---

## 16.6 DOM structure

```text
[children=2]
[descendants>5]
[siblings=3]
[index=1]
[index_of_type=2]
[depth>3]
[text_nodes=1]
```

Indexes are 1-based.

---

## 16.7 Scroll properties

Element values:

```text
[scrollLeft>0px]
[scrollTop>100px]
[scrollWidth>500px]
[scrollHeight>1000px]
[scroll_x>0px]
[scroll_y>0px]
[scroll_x_max>0px]
[scroll_y_max>0px]
[scroll_x_percent>50%]
[scroll_y_percent>50%]
```

Window values:

```text
[scrollX>0px]
[scrollY>100px]
```

---

## 16.8 Attributes

Use:

```text
[attr:name="value"]
```

Example:

```text
button[attr:type="submit"]
```

---

## 16.9 Properties

Use:

```text
[prop:name="value"]
```

Example:

```text
input[prop:value="hello"]
```

---

## 16.10 Dataset

Use:

```text
[data:name="value"]
```

which reads:

```html
data-name="value"
```

---

## 16.11 ARIA attributes

Use:

```text
[aria:expanded="true"]
```

which reads:

```html
aria-expanded="true"
```

---

## 16.12 Computed CSS properties

Unknown predicate names fall through to computed CSS style lookup.

Camel case is converted to kebab case.

Examples:

```text
[color="rgb(0, 0, 0)"]
[display="flex"]
[position="absolute"]
[backgroundColor="rgb(255, 255, 255)"]
```

---

# 17. Relative-to-parent predicates

These keys are handled specially:

```text
[x_rel>20px]
[y_rel>20px]
[x_ref>20px]
[y_ref>20px]
```

When `%` is used, the value is normalized to the parent dimension.

Example:

```text
[x_rel>50%]
```

means the candidate's left position is beyond half of the parent's width.

For bare predicates, `x_ref`/`y_ref` currently behave like parent-relative values.

---

# 18. Explicit reference predicates

Syntax:

```text
[key(reference) operator value]
```

Example:

```text
[x(.sidebar)>20px]
```

Reference expressions can be:

```text
parent
prev
next
siblings
closest:<selector>
<any CSS selector>
```

Examples:

```text
[x(parent)>20px]
[y(prev)>10px]
[distance(.target)<100px]
[z_ref(.modal)="front"]
```

---

# 19. Reference geometry properties

The geometry subsystem exposes:

```text
left
right
top
bottom
center_x
center_y
gap_left
gap_right
gap_top
gap_bottom
overlap_x
overlap_y
width_ratio
height_ratio
x_percent
y_percent
distance
intersection
inside
contains_geometry
```

Aliases:

```text
x_ref -> x_percent
y_ref -> y_percent
x -> left
y -> top
cx -> center_x
cy -> center_y
```

### Important `x_ref` / `y_ref` note

With an explicit reference, `x_ref` and `y_ref` map to percentage geometry. This differs from the bare parent-relative handling. Consumers requiring unambiguous semantics should prefer explicit property names such as:

```text
x_percent
left
y_percent
top
```

---

# 20. Stacking order

Use:

```text
[z_ref="front"]
[z_ref="back"]
```

or:

```text
[z_ref(.overlay)="front"]
```

Possible values include:

```text
front
back
same
unknown
none
```

The implementation:

1. checks rectangle overlap;
2. samples the overlap region;
3. calls `document.elementsFromPoint()`;
4. compares paint-stack positions.

This is a useful practical approximation, not a complete browser stacking-context proof system.

---

# 21. Boolean operators

## `and()`

```text
and(A, B, ...)
```

Element must match every expression.

---

## `or()`

```text
or(A, B, ...)
```

Element must match at least one expression.

---

## `not()`

```text
not(A)
```

Universe complement.

Shorthand:

```text
!(A)
```

---

## `nand()`

```text
nand(A, B, ...)
```

Matches unless all operands match.

---

## `nor()`

```text
nor(A, B, ...)
```

Matches when no operand matches.

---

## `xor()`

```text
xor(A, B, ...)
```

Matches when exactly one operand matches.

---

## `xnor()`

```text
xnor(A, B, ...)
```

Current set semantics match when either none or all operands match.

---

# 22. `apply()`

```text
apply(base, expression)
```

Creates a scope consisting of each matching base element plus all of its descendants, then evaluates the second expression in that scope.

Example:

```text
apply(
    .dialog,
    button[visible=true]
)
```

---

# 23. `has()`

```text
has(base, condition)
```

Returns base elements having at least one matching descendant.

The base itself is not included in the descendant condition universe.

Example:

```text
has(
    .card,
    button[innerText="Save *"]
)
```

---

# 24. Ordered `children()`

```text
children(base, child1, child2, ...)
```

This operator is strict:

1. the base must have exactly the specified number of direct element children;
2. each child must match the condition at the same position.

Example:

```text
children(
    .card,
    .title[textContent="Order *"],
    button[innerText="Save *"]
)
```

matches:

```html
<div class="card">
    <div class="title">Order 1</div>
    <button>Save order</button>
</div>
```

but not a card containing an additional third child.

---

# 25. `child()`

```text
child(base, index, condition)
```

Checks one direct child by 1-based index.

Example:

```text
child(.card, 2, button)
```

Other children are unrestricted.

---

# 26. Sibling relations

## `sibling()` / `siblings()`

```text
sibling(base, condition)
siblings(base, condition)
```

Current implementation treats both as "has any sibling matching condition".

---

## `prev()`

```text
prev(base, condition)
```

Tests the immediately preceding element sibling.

---

## `next()`

```text
next(base, condition)
```

Tests the immediately following element sibling.

---

# 27. Parent and ancestor relations

## `parent()`

```text
parent(base, condition)
```

Tests the direct parent.

---

## `ancestor()`

```text
ancestor(base, condition)
```

Tests ancestors up to the engine root.

---

## `closest()`

```text
closest(base, condition)
```

### Current limitation

The current implementation only tests the first collected ancestor, effectively the immediate parent. It does not yet perform a true nearest-matching-ancestor search.

Use `ancestor()` when full ancestor traversal is required.

---

# 28. Document order

## `before()`

```text
before(base, reference)
```

Returns bases occurring before at least one reference in document order.

## `after()`

```text
after(base, reference)
```

Returns bases occurring after at least one reference.

---

# 29. Spatial operators

## `left_of()`

```text
left_of(base, reference)
left_of(base, reference, tolerance)
```

## `right_of()`

```text
right_of(base, reference[, tolerance])
```

## `above()`

```text
above(base, reference[, tolerance])
```

## `below()`

```text
below(base, reference[, tolerance])
```

## `overlaps()`

```text
overlaps(base, reference)
```

Tests rectangle overlap.

## `inside()`

```text
inside(base, reference)
```

Tests complete geometric containment.

## `near()`

```text
near(base, reference, distance)
```

Uses center-point Euclidean distance.

## `aligned_left()`

```text
aligned_left(base, reference, tolerance)
```

## `aligned_center_x()`

```text
aligned_center_x(base, reference, tolerance)
```

### Distance units

The optional distance/tolerance arguments are currently parsed numerically with `parseFloat()` and therefore behave as CSS-pixel-like numeric tolerances rather than a general unit system.

---

# 30. Quantifiers

Syntax:

```text
any(base, relation, condition)
all(base, relation, condition)
none(base, relation, condition)
```

Supported relation tokens:

```text
children
descendants
siblings
```

Example:

```text
any(
    .toolbar,
    children,
    button[disabled=true]
)
```

`any` requires at least one hit.

`all` requires a non-empty candidate relation and every candidate to match.

`none` requires zero hits.

The implementation deliberately does not use vacuous truth for `all` on an empty candidate set.

---

# 31. Shadow DOM

```text
shadow(base, condition)
```

Queries inside each matching base's **open** shadow root.

Example:

```text
shadow(
    my-component,
    button[visible=true]
)
```

Closed shadow roots cannot be traversed through normal browser APIs and are not supported.

---

# 32. Slots

```text
slot(base, condition)
```

The base must be an `HTMLSlotElement`.

Assigned elements are retrieved using:

```js
assignedElements({
    flatten: true
})
```

and then evaluated against the condition.

---

# 33. Pseudo-elements

```text
pseudo(base, before|after, condition)
```

Example:

```text
pseudo(
    .required,
    before,
    [content!="none"]
)
```

The current implementation supports a single computed-style predicate in the third argument.

It does not evaluate a full arbitrary ExtendedSelector expression against a pseudo-element because pseudo-elements are not DOM `Element` objects.

---

# 34. Custom predicates

Register a custom predicate value resolver:

```js
engine.registerPredicate("word_count", (element) =>
    (element.textContent ?? "")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .length
);
```

Then:

```text
article[word_count>100]
```

Resolver signature:

```js
(element, {
    engine,
    key
}) => unknown
```

The returned value is converted to a string before comparison.

Remove it with:

```js
engine.unregisterPredicate("word_count");
```

---

# 35. Custom operators

Register:

```js
engine.registerOperator("first", ({
    engine,
    args,
    universe
}) => engine.evaluateAst(args[0], universe).slice(0, 1));
```

Use:

```text
first(.card)
```

Handler context:

```js
{
    engine,
    node,
    universe,
    args,
    raw
}
```

Remove:

```js
engine.unregisterOperator("first");
```

Custom operator names are normalized to lowercase.

---

# 36. Reference resolution API

```js
engine.resolveReference(element, expression)
```

Examples:

```js
engine.resolveReference(element, "parent");
engine.resolveReference(element, "prev");
engine.resolveReference(element, ".toolbar");
engine.resolveReference(element, "closest:.panel");
```

Invalid CSS references throw `SyntaxError`.

---

# 37. Low-level predicate API

```js
engine.predicateValue(element, key)
```

Returns the observed value used by a predicate.

Example:

```js
engine.predicateValue(element, "visible");
engine.predicateValue(element, "width");
```

Custom predicate resolvers are checked first.

---

# 38. Low-level atom evaluation

```js
engine.extendedAtom(expression, universe?)
```

Evaluates one CSS atom plus extended predicates.

Example:

```js
engine.extendedAtom(
    'button[innerText="Save *"][visible=true]'
);
```

---

# 39. Low-level AST evaluation

```js
engine.evaluateAst(ast, universe)
```

Evaluates an already parsed AST.

Normally use `query()` unless implementing integrations or custom operators.

---

# 40. `evaluateExtended()`

```js
engine.evaluateExtended(expression, universe?)
```

Parses with `parseExtended()` and evaluates immediately.

Unlike `query()`, it bypasses the normal lint-first parsing path.

---

# 41. Utility APIs

## `escape()`

```js
ExtendedSelector.escape(value)
```

Delegates to:

```js
CSS.escape()
```

---

## `wildcardRegex()`

```js
ExtendedSelector.wildcardRegex(pattern)
```

Builds the anchored regex used by wildcard comparisons.

---

## `color()`

```js
ExtendedSelector.color(cssColor)
```

Uses the browser to normalize a CSS color into an RGBA tuple.

---

## `colorSimilarity()`

```js
ExtendedSelector.colorSimilarity(
    actual,
    expected,
    similarity
)
```

---

## `stacking()`

```js
ExtendedSelector.stacking(element, reference)
```

Returns the practical stacking relationship.

---

## `compareValue()`

```js
ExtendedSelector.compareValue(
    actual,
    operator,
    expected
)
```

Central value comparator.

---

## `unitValue()`

```js
ExtendedSelector.unitValue(value, reference?)
```

Resolves `%` against a numeric reference; otherwise uses `parseFloat()`.

---

## `geometry()`

```js
ExtendedSelector.geometry(element, reference)
```

Returns all calculated reference geometry measurements.

---

# 42. Formula-style frontend editor

The editor is optional. The engine does not depend on it.

HTML:

```html
<textarea id="selector">
children(
    .card,
    .title[textContent="Order *"],
    button[innerText="Save *"]
)
</textarea>
```

JavaScript:

```js
import ExtendedSelector from "./extended-selector.js";
import ExtendedSelectorEditor from "./extended-selector-editor.js";

const engine = new ExtendedSelector(document);

const editor = new ExtendedSelectorEditor(
    document.querySelector("#selector"),
    {engine}
);
```

The original textarea is hidden and synchronized.

The visible editor becomes the interactive expression surface.

---

# 43. Editor interaction model

The frontend follows a spreadsheet/formula-editor model.

Functions are rendered as nested capsules:

```text
children ▾ (
    .card,
    not ▾ (
        button[disabled=true]
    )
)
```

Important characteristics:

- operators are dropdown controls;
- parentheses visually bound the nested call;
- nested calls create nested capsules;
- atoms are directly editable;
- caret insertion points exist around structural tokens;
- clicking a parenthesis highlights its matching call;
- expressions serialize back to source automatically.

---

# 44. Editor value

Read:

```js
editor.value
```

Write:

```js
editor.value = "and(.a, .b)";
```

The hidden textarea is kept synchronized.

---

# 45. Editor engine binding

```js
editor.setEngine(engine);
```

The engine is used for live lint diagnostics.

---

# 46. Operator dropdowns

Operators such as:

```text
and
or
not
children
has
inside
near
```

are controls rather than static text.

Selecting a replacement updates the call's structural operator and serialized source.

---

# 47. Caret stops

The editor creates editable insertion positions:

- before a top-level expression;
- after a top-level expression;
- before arguments;
- between arguments;
- after arguments.

This permits expression insertion at structural boundaries rather than restricting editing to predefined text pills.

---

# 48. Wrapping expressions

Programmatically:

```js
editor.wrapNode(node, "and");
```

or:

```js
editor.wrapSelection("and");
```

Conceptually:

```text
A
```

becomes:

```text
and(A, |)
```

where `|` is the focused insertion position.

This is intended to mirror formula-editor behavior when an existing expression is promoted into an argument of a new function.

---

# 49. Editor events

The editor dispatches:

```text
change
```

with detail:

```js
{
    value,
    diagnostics
}
```

Example:

```js
editor.addEventListener("change", ({detail}) => {
    console.log(detail.value);
    console.log(detail.diagnostics);
});
```

---

# 50. Editor CSS customization

The supplied stylesheet uses CSS custom properties including:

```css
--ese-bg
--ese-fg
--ese-line
--ese-line-strong
--ese-blue
--ese-green
--ese-purple
--ese-hover
--ese-focus
--ese-error
```

Override them at an appropriate scope:

```css
.selector-editor {
    --ese-bg: #111;
    --ese-fg: #eee;
    --ese-line: #444;
}
```

The editor uses ordinary DOM elements and can be further themed with `.ese-*` selectors.

---

# 51. Complex examples

## Visible save button inside a card

```text
has(
    .card[visible=true],
    button[innerText="Save *"][enabled=true]
)
```

---

## Exact ordered card structure

```text
children(
    article.card,
    h2.title[textContent="Order *"],
    button[innerText="Save *"]
)
```

---

## Card with no disabled buttons

```text
none(
    .card,
    descendants,
    button[disabled=true]
)
```

---

## Card where every direct child is visible

```text
all(
    .card,
    children,
    [visible=true]
)
```

---

## Button near a dialog

```text
near(
    button.action,
    .dialog,
    100
)
```

---

## Button below a heading

```text
below(
    button,
    h2,
    10
)
```

---

## Open Shadow DOM

```text
shadow(
    user-panel,
    button[innerText="Save *"]
)
```

---

## Pseudo-element style

```text
pseudo(
    .required,
    before,
    [content!="none"]
)
```

---

## Boolean nesting

```text
and(
    .card[visible=true],
    or(
        has(.card, button.primary),
        has(.card, a.action)
    ),
    not(
        has(.card, [disabled=true])
    )
)
```

---

# 52. Registration as native CSS hooks

A useful integration pattern is to materialize a query result onto the DOM using a normal attribute:

```js
const card = engine.queryOne(`
    children(
        .card,
        .title[textContent="Order *"],
        button[innerText="Save *"]
    )
`);
```

Then:

```js
card?.setAttribute("extended-selector", "card");
```

Normal CSS can subsequently use:

```css
[extended-selector="card"] > svg {
    /* ... */
}
```

Likewise native JavaScript can use:

```js
document.querySelector(
    '[extended-selector="card"] > svg'
);
```

If a project adds a convenience registration property/API around this pattern, the resulting selector remains ordinary CSS because the registration is represented by a real DOM attribute.

---

# 53. Grammar summary

Conceptually:

```text
expression :=
    atom
  | call
  | !(expression)

call :=
    operator(expression, ...)
```

An atom is:

```text
CSS-selector + zero-or-more extended predicates
```

Predicate:

```text
[key operator value]
```

Reference predicate:

```text
[key(reference) operator value]
```

The parser is deliberately lightweight. It is not currently implemented as a formal token-stream parser with source spans on every AST node.

---

# 54a. Public signatures

`ExtendedSelector.SIGNATURES` is a frozen table, one entry per operator, that `lint()` reads for argument counts and editors read to name empty argument slots:

```js
ExtendedSelector.SIGNATURES.has;
// { min: 2, max: 2, roles: ["base", "condition"], optionalFrom: 2,
//   kinds: ["selector", "expression"], summary: "…" }
ExtendedSelector.SIGNATURES.and.variadicRole; // "expression"
```

| Field | Meaning |
| --- | --- |
| `min`, `max` | Accepted argument counts (`max` may be `Infinity`) |
| `roles` | Role of each argument in order, for example `base`, `condition`, `index`, `reference`, `distance` |
| `optionalFrom` | Index of the first optional argument (equals `min`) |
| `kinds` | `selector`, `expression`, `number`, `string`, `tolerance` or `keys` per role |
| `variadicRole` | Role repeated for arguments past the listed roles (`and`, `children`, `sort`) |

`ExtendedSelector.CAPABILITIES.predicateTypes` maps each built-in predicate key to `text`, `boolean` or `number`.

---

# 54b. Diagnostic severity, ranges and suggestions

Every `SelectorDiagnostic` has `severity` (`"error"` or `"warning"`). `lint(expression)` returns errors only, as before; `lint(expression, { warnings: true })` also returns warnings. Optional fields: `suggestion` (`{offset, length, text}`, the one-click replacement) and `role` (the first missing argument role of an arity error).

| Code | Severity | Meaning |
| --- | --- | --- |
| `unknown-pseudo` | error | Unknown pseudo-class or pseudo-element; range is the token, suggestion is the nearest known name |
| `unknown-operator` | error | Unknown operator; suggestion is the nearest operator |
| `pseudo-element-unmatchable` | warning | A pseudo-element cannot be matched from script; use `pseudo(sel, "::before", expr)` |
| `visited-unmatchable` | warning | `:visited` never matches from script |

`CAPABILITIES.cssPseudoClasses` and `cssPseudoElements` list the names used for suggestions.

---

# 54. Operator arity

| Operator | Arity |
|---|---:|
| `not` | 1 |
| `apply` | 2 |
| `has` | 2 |
| `sibling` | 2 |
| `siblings` | 2 |
| `prev` | 2 |
| `next` | 2 |
| `parent` | 2 |
| `ancestor` | 2 |
| `closest` | 2 |
| `child` | 3 |
| `before` | 2 |
| `after` | 2 |
| `any` | 3 |
| `all` | 3 |
| `none` | 3 |
| `shadow` | 2 |
| `slot` | 2 |
| `pseudo` | 3 |
| `and` | 2+ |
| `or` | 2+ |
| `nand` | 2+ |
| `nor` | 2+ |
| `xor` | 2+ |
| `xnor` | 2+ |
| `children` | 2+ |
| `left_of` | 2–3 |
| `right_of` | 2–3 |
| `above` | 2–3 |
| `below` | 2–3 |
| `overlaps` | evaluator accepts 2–3 |
| `inside` | evaluator accepts 2–3 |
| `near` | 2–3 |
| `aligned_left` | 2–3 |
| `aligned_center_x` | 2–3 |

For spatial functions where a third argument is accepted but unused by a particular operation, prefer the documented minimal form.

---

# 55. Error handling

Normal query code should use:

```js
try {
    const result = engine.query(expression);
} catch (error) {
    if (error instanceof SyntaxError)
        console.error(error.message);
}
```

For editor/live-validation scenarios, prefer:

```js
const diagnostics = engine.lint(expression);
```

because it returns structured errors rather than using exceptions as control flow.

---

# 56. Performance guidance

## Parse once for repeated queries

Prefer:

```js
const queryVisibleCards = engine.compile(
    ".card[visible=true]"
);

queryVisibleCards();
queryVisibleCards();
```

over reparsing the same source repeatedly.

## Restrict the root

Instead of:

```js
new ExtendedSelector(document);
```

use a relevant subtree when possible:

```js
new ExtendedSelector(
    document.querySelector("#workspace")
);
```

## Geometry is more expensive than pure CSS

Queries involving:

- `getBoundingClientRect()`;
- `getComputedStyle()`;
- viewport calculations;
- stacking;
- color normalization;

cost more than plain CSS matching.

## Layout-sensitive queries can trigger layout work

Batch queries where possible and avoid running geometry-heavy selectors unnecessarily on every animation frame.

---

# 57. Security considerations

The engine does not execute arbitrary JavaScript from selector expressions.

However:

- expressions can trigger broad DOM traversal;
- expensive nested queries can consume significant CPU;
- selectors supplied by untrusted users should have complexity limits in hostile/multi-tenant environments;
- custom predicate/operator callbacks are executable application code and therefore inherit the trust level of the application registering them.

The engine is not a sandbox.

---

# 58. Browser scope

The implementation expects modern browser APIs including:

- ES modules;
- `EventTarget`;
- `CustomEvent`;
- `Element.matches`;
- `querySelectorAll`;
- `getBoundingClientRect`;
- `getComputedStyle`;
- `CSS.escape`;
- `document.elementsFromPoint`;
- `ShadowRoot`;
- `HTMLSlotElement`;
- `Set`;
- modern array/string methods.

The editor additionally uses:

- `contenteditable`;
- Selection/Range APIs;
- `document.execCommand("insertText", ...)` in the current implementation.

`execCommand` is legacy browser API territory and is a candidate for future replacement with explicit Range editing.

---

# 59. Current limitations and known semantics

This section is intentionally explicit.

## Parser

The parser is lightweight and based on balanced splitting/regex recognition rather than a full tokenizer with exact source spans.

Repeated identical subexpressions can therefore make some lint positions approximate.

## Lint CSS stripping

Extended predicates are stripped before native CSS validation using regular-expression logic. Extremely complex bracket/quote combinations can expose edge cases.

## Units

There is no complete CSS Typed OM unit-conversion layer.

## Accessible names

Accessible-name and implicit-role handling are approximations.

## Visibility

Visibility is heuristic and does not prove actual pixel visibility.

## Stacking

Stacking uses a sampled `elementsFromPoint()` approach.

## Closed Shadow DOM

Not accessible.

## Cross-origin frames

Not traversed.

## Temporal predicates

There is no built-in:

```text
changed(...)
stable(...)
appeared(...)
```

or historical state engine.

## `count(...)`

The public JavaScript `count()` method works.

The expression-level `count(...)` branch is intentionally not usable and directs callers toward structural numeric predicates or `any/all/none`.

## `closest()`

Current operator semantics test only the first ancestor candidate rather than finding the first ancestor satisfying the condition.

## Reference percentages

Explicit `x_ref` / `y_ref` map to percentage geometry, while bare versions use parent-relative handling.

## Pseudo-elements

Only computed-style predicate matching is supported.

## Synchronous core

The engine does not wait for future DOM state.

---

# 60. Features intentionally not represented as claims

The current implementation should not be described as providing the following unless they are added later:

- complete CSS unit conversion;
- complete accessibility tree semantics;
- full occlusion testing;
- closed-shadow traversal;
- cross-origin frame traversal;
- temporal observation;
- event-listener introspection;
- regex text operators;
- fuzzy-text operators;
- complete `count(...)` expression semantics;
- full predicate proof-tree explanations;
- a formal standards-grade parser/tokenizer;
- async waiting/observation APIs.

---

# 61. Recommended future extensions

Natural next steps include:

1. A real tokenizer with exact source spans.
2. AST nodes carrying `start` and `end`.
3. A dedicated `ExtendedSelectorSyntaxError`.
4. Browser-document context derived from `root.ownerDocument`.
5. Elimination of global `document`/`window` assumptions.
6. Typed units and CSS Typed OM integration.
7. Correct true-closest semantics.
8. A real relational `count(...)`.
9. `contains`, `startsWith`, `endsWith`, regex and fuzzy text predicates.
10. `observe(expression, callback)`.
11. `waitFor(expression, options)`.
12. Per-predicate explanation/proof trees.
13. TypeScript declarations.
14. A global/IIFE browser build in addition to ES modules.
15. Dedicated browser-runtime tests.
16. Mutation/resize/scroll-aware query caching.
17. Better accessibility semantics.
18. Explicit frame/shadow scopes.
19. Editor undo/redo at structural-operation level.
20. Editor keyboard navigation between pill boundaries without relying on legacy editing APIs.

---

# 62. Suggested application architecture

For large applications:

```js
const selectors = new ExtendedSelector(
    document.querySelector("#app")
);

const queries = {
    saveOrder: selectors.compile(
        'button[innerText="Save *"][enabled=true]'
    ),
    orderCard: selectors.compile(`
        children(
            .card,
            .title[textContent="Order *"],
            button[innerText="Save *"]
        )
    `)
};
```

Then:

```js
const card = queries.orderCard()[0] ?? null;
```

This keeps selector definitions centralized and parses reusable selectors only once.

---

# 63. Custom domain predicates

Application-specific state is often better exposed through custom predicates than encoded into increasingly complex CSS.

Example:

```js
engine.registerPredicate(
    "dirty",
    (element) => element.matches("[data-dirty=true]")
);
```

Then:

```text
form[dirty=true]
```

Or:

```js
engine.registerPredicate(
    "model_id",
    (element) => element.dataset.modelId ?? ""
);
```

Then:

```text
.card[model_id="42"]
```

This keeps domain semantics inside application code while preserving a compact query language.

---

# 64. Testing recommendations

At minimum, test:

- plain CSS atoms;
- every comparison operator;
- wildcard values;
- quoted commas;
- nested calls;
- deeply nested calls;
- malformed parentheses;
- malformed brackets;
- unterminated strings;
- operator arity;
- custom predicates;
- custom operators;
- ordered children;
- sibling/ancestor relations;
- spatial operations;
- viewport predicates;
- scrolling predicates;
- Shadow DOM;
- slots;
- pseudo-element styles;
- color similarity;
- editor serialization;
- editor nested wrapping;
- editor operator replacement;
- editor caret-boundary insertion;
- lint/query agreement.

For geometry tests, use a real browser rather than a DOM-only test implementation because layout APIs are required.

---

# 65. Debugging workflow

Start with:

```js
const validation = engine.validate(expression);
console.log(validation);
```

Then inspect parsing:

```js
console.dir(
    engine.parse(expression),
    {depth: null}
);
```

For a single atom:

```js
console.log(
    engine.extendedAtom(
        'button[visible=true]'
    )
);
```

For a predicate:

```js
console.log(
    engine.predicateValue(
        element,
        "visible"
    )
);
```

For geometry:

```js
console.log(
    ExtendedSelector.geometry(
        element,
        reference
    )
);
```

For final results:

```js
console.log(
    engine.explain(expression)
);
```

---

# 66. Expression style guide

For maintainable selectors, format nested expressions vertically:

```text
and(
    .card[visible=true],
    has(
        .card,
        button[
            innerText="Save *"
        ]
    )
)
```

For actual predicate syntax, keep each bracket expression syntactically contiguous unless the parser/editor version explicitly supports multiline predicate internals.

Prefer semantic predicates:

```text
button[accessible_name="Save"]
```

over fragile positional geometry when both express the same intent.

Prefer structural relations over long CSS `:nth-child()` chains when the structure itself is what matters.

Prefer compiled expressions for frequently repeated queries.

---

# 67. API reference summary

```js
new ExtendedSelector(root?, options?)

engine.configure(options)
engine.setRoot(root)

engine.registerPredicate(name, resolver)
engine.unregisterPredicate(name)

engine.registerOperator(name, handler)
engine.unregisterOperator(name)

engine.universe(root?)

engine.query(expression, options?)
engine.queryOne(expression, options?)
engine.count(expression, options?)
engine.exists(expression, options?)
engine.matches(element, expression)
engine.filter(elements, expression)

engine.lint(expression)
engine.formatDiagnostic(diagnostic)
engine.parse(expression)
engine.parseExtended(expression)
engine.validate(expression)
engine.compile(expression)
engine.explain(expression, options?)

engine.resolveReference(element, expression)
engine.referencePredicate(element, key, reference, operator, expected)
engine.predicateValue(element, key)
engine.extendedAtom(expression, universe?)
engine.evaluateAst(ast, universe)
engine.evaluateExtended(expression, universe?)

ExtendedSelector.position(expression, offset)
ExtendedSelector.diagnostic(expression, message, offset?, length?, code?)
ExtendedSelector.syntaxError(expression, message, offset?, length?, code?)
ExtendedSelector.escape(value)
ExtendedSelector.splitTopLevel(value, delimiter?)
ExtendedSelector.wildcardRegex(pattern)
ExtendedSelector.color(value)
ExtendedSelector.colorSimilarity(actual, expected, similarity)
ExtendedSelector.stacking(element, reference)
ExtendedSelector.compareValue(actual, operator, expected)
ExtendedSelector.unitValue(value, reference?)
ExtendedSelector.geometry(element, reference)
```

Editor:

```js
new ExtendedSelectorEditor(textarea, options?)

editor.value
editor.value = expression

editor.setEngine(engine)
editor.wrapSelection(operator?)
editor.wrapNode(node, operator?)
```

---

# 68. Complete operator index

```text
and
or
not
nand
nor
xor
xnor

apply
has
children
child

sibling
siblings
prev
next
parent
ancestor
closest

before
after

left_of
right_of
above
below
overlaps
inside
near
aligned_left
aligned_center_x

any
all
none

shadow
slot
pseudo
```

---

# 69. Complete predicate namespace index

Built-in direct keys include:

```text
textContent
innerText
innerHTML
normalizedText
value

role
accessible_name

visible
rendered
enabled
disabled
focused
checked
selected
editable
clickable
draggable
scrollable

in_viewport
viewport_ratio
above_viewport
below_viewport

width
height
area
aspect_ratio

x_abs
y_abs
right_abs
bottom_abs
center_x_abs
center_y_abs
x_view
y_view
distance_to_viewport_top

children
descendants
siblings
index
index_of_type
depth
text_nodes

scrollLeft
scrollTop
scrollWidth
scrollHeight
scrollX
scrollY
scroll_x
scroll_y
scroll_x_max
scroll_y_max
scroll_x_percent
scroll_y_percent

x_rel
y_rel
x_ref
y_ref
z_ref
```

Namespaces:

```text
attr:<name>
prop:<name>
data:<name>
aria:<name>
```

Unknown keys are interpreted as computed-style properties.

---

# 70. Final notes

`ExtendedSelector` is best understood as a composable query DSL layered over the browser DOM rather than as a replacement for CSS.

Use native CSS whenever native CSS expresses the requirement cleanly. Use extended predicates for values/state that CSS cannot directly express. Use structural and spatial operators when relationships are the requirement. Use custom predicates/operators for application-domain semantics.

The frontend editor is a separate UX layer: expressions remain plain serializable text, so they can be stored, transmitted, diffed, tested, generated programmatically, or executed without the editor.

That separation is intentional:

```text
structured editor
      ↓
serialized expression
      ↓
lint / parse
      ↓
AST
      ↓
evaluation
      ↓
DOM elements
```

This makes the expression language usable both interactively and programmatically while keeping the core engine independent of its visual authoring interface.

---

# Consolidated ExtendedSelector API — v2.0.0

This section updates the documentation for the consolidated `ExtendedSelector`
implementation. It is normative for features added after the original
frontend/editor documentation.

## Registration

Every element returned by `query()` is decorated with a non-enumerable
`register` property backed by the `extended-selector` attribute.

```js
const engine = new ExtendedSelector(document);
const save = document.querySelector("#save");

engine.register(save, "save-button");
save.register; // "save-button"
save.register = "primary-save";
engine.unregister(save);
```

The equivalent selector is:

```css
[extended-selector="save-button"]
```

Registered selectors also participate in selector generation/ranking.

## Selector generation and ranking

`bestSelector(target, options)` evaluates selector candidates and returns the
best exact candidate together with the ranked candidate set.
`generateSelector(target, options)` is the convenience selector-generation
entry point.

Candidate sources supported by the consolidated engine are:

| Source | Integration |
| --- | --- |
| registration | `[extended-selector="…"]` |
| css-selector-generator | `options.generator` |
| optimal-select | `options.optimal` |
| optimal-select optimization | `options.optimal.optimize(...)` |
| @medv/finder | `options.finder` |
| native fallback | built into `ExtendedSelector` |

Third-party generators are injected; the core class does not bundle their
source code.

Example:

```js
const result = engine.bestSelector(button, {
  generator: cssSelectorGenerator,
  optimal: OptimalSelect,
  finder,
});

console.log(result.selector);
console.table(result.candidates);
```

The engine verifies candidates against the target set before ranking them.
Ranking uses specificity, fragility, selector length, deterministic lexical
ordering, and engine identity as deterministic tie-breaking data.

## Comparison operators

The consolidated predicate grammar supports:

| Operator | Meaning | Example |
| --- | --- | --- |
| `=` | equality; `*` in the expected value is a wildcard | `[role=button]` |
| `!=` | inequality | `[content!="none"]` |
| `<` | less than | `[width<500]` |
| `<=` | less than or equal | `[children<=3]` |
| `>` | greater than | `[aspect_ratio>1.5]` |
| `>=` | greater than or equal | `[descendants>=5]` |
| `^=` | string starts with | `[innerText^="Save"]` |
| `$=` | string ends with | `[innerText$="order"]` |
| `*=` | string contains | `[innerText*="warning"]` |
| `~=` | regular expression or color similarity | `[innerText~=/save\s+\w+/i]` |
| `~~` | fuzzy string similarity | `[innerText~~"Save order",0.9]` |

`~=` accepts `/pattern/flags` for regular-expression matching. For color
values it retains the color-similarity form with a similarity threshold.

## Predicate namespaces

```text
[attr:title="Save"]
[prop:disabled=false]
[data:state="open"]
[aria:expanded=true]
```

The namespaces resolve respectively through attributes, DOM properties,
`data-*` attributes, and `aria-*` attributes.

## Text predicates

```text
[innerText^="Save"]
[innerText$="order"]
[innerText*="warning"]
[innerText~=/save\s+\w+/i]
[innerText~~"Save order",0.9]
[normalizedText="Save *"]
[accessible_name="Save *"]
```

The same comparison machinery can be used with `textContent`, `innerText`,
`innerHTML`, `normalizedText`, `value`, `role`, and `accessible_name`.

## State and accessibility predicates

Examples:

```text
input[prop:disabled=false]
[aria:expanded=true]
[role=button]
[role=button][accessible_name="Save *"]
[visible=true]
[rendered=true]
[enabled=true]
[focused=true]
[checked=true]
[selected=true]
[editable=true]
[clickable=true]
[draggable=true]
[scrollable=true]
[in_viewport=true]
```

## Structural predicates

Examples:

```text
.card[children=2]
.card[descendants>=5]
.item[index=2]
.item[index_of_type=1]
[node][siblings>=2]
[node][depth>=3]
[node][text_nodes>0]
```

`index` and `index_of_type` are one-based.

## Geometry and dimensions

Examples:

```text
[width>=320]
[height>40]
[area>10000]
[aspect_ratio>1.5]
[x_abs>=0]
[y_abs>=0]
[x_view>=0]
[y_view>=0]
[viewport_ratio>0.5]
```

Reference geometry uses `[property(reference) operator value]`:

```text
[distance(.target)<50px]
[intersection(.panel)>50%]
[inside(.panel)=true]
[contains_geometry(.badge)=true]
[gap_right(.label)<20]
[overlap_x(.panel)>0]
```

Available geometry values include `left`, `right`, `top`, `bottom`,
`center_x`, `center_y`, `gap_left`, `gap_right`, `gap_top`, `gap_bottom`,
`overlap_x`, `overlap_y`, `width_ratio`, `height_ratio`, `x_percent`,
`y_percent`, `distance`, `intersection`, `inside`, and
`contains_geometry`. `z_ref` performs stacking comparison.

## Spatial operators

```text
left_of(.label, .input, 20)
right_of(.input, .label, 20)
above(.tooltip, .button, 5)
below(.menu, .button, 5)
overlaps(.overlay, .panel)
inside(.badge, .card)
near(.tooltip, .button, 50)
aligned_left(.a, .b, 2)
aligned_center_x(.a, .b, 2)
```

The optional third argument is the distance/tolerance where the corresponding
operator uses one.

## Structural and relational operators

```text
apply(.card, [visible=true])
has(.card, .badge)
parent(.item, .list)
ancestor(.item, .panel)
closest(.item, .panel)
sibling(.item, .active)
prev(.item, .label)
next(.label, .item)
child(.list, 2, .item)
children(.row, .label, .input)
before(.a, .b)
after(.b, .a)
any(.list, children, .active)
all(.list, children, [visible=true])
none(.list, descendants, [disabled=true])
```

`closest()` searches the ancestor chain for the nearest matching ancestor.
`any()`, `all()`, and `none()` accept the relations `children`,
`descendants`, and `siblings`; unknown relation names are errors.

## Boolean composition

```text
and(.button, [visible=true])
or(.primary, .secondary)
not([disabled=true])
!(.disabled)
nand(.a, .b)
nor(.a, .b)
xor(.a, .b)
xnor(.a, .b)
```

Boolean calls can be nested.

## Shadow DOM

Open shadow roots can be traversed explicitly:

```text
shadow(my-widget, button.action)
shadow(my-widget, [role=button][accessible_name="Save *"])
```

Closed shadow roots are not accessible to the browser-native implementation.

## Slots

```text
slot(slot[name=actions], button[visible=true])
```

`slot()` evaluates the condition against assigned elements using
`assignedElements({flatten: true})`.

## Pseudo-elements

```text
pseudo(.item, before, [content!="none"])
pseudo(.item, after, [display="block"])
```

The predicate is evaluated against `getComputedStyle(element, "::before")`
or `::after`.

## Custom predicates

```js
engine.registerPredicate("test-id", (element) =>
  element.getAttribute("data-testid") ?? ""
);

engine.query('[test-id="save"]');

engine.unregisterPredicate("test-id");
```

A predicate resolver receives the element plus `{engine, key}`.

## Custom operators

```js
engine.registerOperator("first", ({engine, args, universe}) =>
  engine.evaluateAst(args[0], universe).slice(0, 1)
);

engine.query("first(.item)");
engine.unregisterOperator("first");
```

Custom operators receive the engine, AST node, universe, parsed arguments,
and raw arguments.

## Parsing, validation, diagnostics, and compilation

```js
engine.lint(expression);
engine.validate(expression);
engine.parse(expression);
engine.compile(expression);
engine.explain(expression);
engine.formatDiagnostic(diagnostic);
```

`compile()` returns a reusable function with `.ast` and `.expression`
properties.

```js
const visibleButtons = engine.compile(
  'and([role=button], [visible=true])'
);

const matches = visibleButtons();
```

Diagnostics include code, message, absolute offset, line, column, source line,
length, and a caret pointer.

## Query API

```js
engine.query(expression);
engine.queryOne(expression);
engine.count(expression);
engine.exists(expression);
engine.matches(element, expression);
engine.filter(elements, expression);
engine.evaluateExtended(expression);
engine.universe();
```

`query()` deduplicates and document-orders results by default and emits a
`query` event containing the expression, AST, matched elements, count, and
duration.

## Configuration

```js
const engine = new ExtendedSelector(document, {
  strict: true,
  deduplicate: true,
  sortDocumentOrder: true,
});

engine.configure({
  deduplicate: false,
});

engine.setRoot(container);
```

## Capability discovery

The consolidated class exposes a frozen capability manifest:

```js
ExtendedSelector.VERSION;      // "2.0.0"
ExtendedSelector.CAPABILITIES;
```

`CAPABILITIES` enumerates comparison, boolean, structural, spatial, DOM,
generator, namespace, and reference-geometry families.

## Local third-party selector libraries

The selector generators are optional dependencies. A local npm project can
install them with:

```bash
npm install css-selector-generator optimal-select @medv/finder
```

There is no separate “optimized optimal-select” package: optimization is
provided by `optimal-select` itself through its optimization API.

For an offline deployment, install the packages once and retain the required
local package files (or the project's `node_modules`/bundled equivalents)
alongside the application.

## Complete examples

```js
const engine = new ExtendedSelector(document);

engine.query('right_of(.input, .label, 20)');
engine.query('above(.tooltip, .button, 5)');
engine.query('overlaps(.overlay, .panel)');
engine.query('inside(.badge, .card)');
engine.query('near(.tooltip, .button, 50)');
engine.query('aligned_left(.a, .b, 2)');

engine.query('.card[children=2]');
engine.query('.card[descendants>=5]');
engine.query('.item[index=2]');
engine.query('.item[index_of_type=1]');

engine.query('input[prop:disabled=false]');
engine.query('[aria:expanded=true]');
engine.query('[data:state="open"]');
engine.query('[role=button][accessible_name="Save *"]');

engine.query('shadow(my-widget, button.action)');
engine.query('slot(slot[name=actions], button[visible=true])');
engine.query('pseudo(.item, before, [content!="none"])');

engine.query('[distance(.target)<50px]');
engine.query('[intersection(.panel)>50%]');
engine.query('[inside(.panel)=true]');
engine.query('[contains_geometry(.badge)=true]');

engine.query('[innerText^="Save"]');
engine.query('[innerText$="order"]');
engine.query('[innerText*="warning"]');
engine.query('[innerText~=/save\\s+\\w+/i]');
engine.query('[innerText~~"Save order",0.9]');
engine.query('[aspect_ratio>1.5]');
```

### Grammar note

Function expressions and CSS/extended atoms are separate AST expressions.
Compose conditions with the explicit function grammar (`and`, `or`, `apply`,
`has`, etc.) rather than relying on undocumented adjacency between a function
call and a following CSS atom.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/extended_selector/`](../exactus/packages/extended_selector/) | [`exactus/tests/packages/extended_selector/`](../exactus/tests/packages/extended_selector/) | [`DOCS.md`](../exactus/docs/packages/extended_selector/DOCS.md) |

[< Packages-exactus_mcp](Packages-exactus_mcp.md) · [Packages index](Packages.md) · [Packages-external >](Packages-external.md)
