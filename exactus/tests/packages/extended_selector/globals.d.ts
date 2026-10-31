/** Globals the fixture page publishes for `engine.test.mjs`. */

/** The engine instance the fixture builds over its own document. */
declare var engine: any;

/** The engine class, for the tests that build their own instances. */
declare var ExtendedSelector: any;

/** Set once the fixture has imported the engine module. */
declare var engineReady: boolean | undefined;

/** The mounted structured-editor instance from `editor-fixture.html`. */
declare var editor: any;

/** The structured-editor class and its static helpers. */
declare var Editor: any;

/** Set once the editor fixture has mounted its editor. */
declare var editorReady: boolean | undefined;

/** Page-side nullable-lookup guard published by the editor fixtures. */
declare var must: <T>(value: T | null | undefined) => T;
