/** Globals the widget-selector demo fixtures publish. */

/** Set once the demo host fixture has mounted. */
declare var hostReady: boolean | undefined;

/** Set once the editor-wrapper fixture has mounted. */
declare var wrapperReady: boolean | undefined;

/** The `createDemoHost` controller mounted by `host-fixture.html`. */
declare var demoHost: any;

/** The widget-editor wrapper class mounted by `wrapper-fixture.html`. */
declare var EditorClass: any;

/** Page-side nullable-lookup guard published by the demo fixtures. */
declare var must: <T>(value: T | null | undefined) => T;
