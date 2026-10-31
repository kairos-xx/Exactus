/** @file Rendered scene inspection and binary export. */
"use strict";
const evidenceGlobal =
  /** @type {typeof globalThis & Record<string, unknown> & {htmlToImage?: {toCanvas: (element: Element, options: Record<string, unknown>) => Promise<HTMLCanvasElement>}, __evidenceSha256?: (buffer: ArrayBuffer) => Promise<ArrayBuffer>}} */ (
    /** @type {unknown} */ (globalThis)
  );
/**
 * JSON-compatible primitive value carried by scene evidence.
 * @typedef {null|boolean|number|string} ScenePrimitiveValue
 */
/**
 * JSON-compatible value carried by scene evidence.
 * @typedef {ReturnType<JSON["parse"]>} SceneValue
 */
/**
 * Serializable scene evidence record.
 * @typedef {{[key:string]:SceneValue}} SceneRecord
 */
/**
 * CSS-pixel point.
 * @typedef {object} ScenePoint
 * @property {number} x Horizontal coordinate.
 * @property {number} y Vertical coordinate.
 */
/**
 * Absolute CSS-pixel rectangle.
 * @typedef {object} SceneRect
 * @property {number} left Left edge.
 * @property {number} top Top edge.
 * @property {number} right Right edge.
 * @property {number} bottom Bottom edge.
 * @property {number} width Width.
 * @property {number} height Height.
 */
/**
 * Rectangle normalized relative to a reference frame.
 * @typedef {object} SceneFrame
 * @property {number} x Normalized left offset.
 * @property {number} y Normalized top offset.
 * @property {number} width Normalized width.
 * @property {number} height Normalized height.
 */
/**
 * RGBA sample.
 * @typedef {[number, number, number, number]} SceneRgba
 */
/**
 * Scroll evidence for one axis.
 * @typedef {object} SceneScrollAxis
 * @property {boolean} scrollable Whether the axis can scroll.
 * @property {number} position Normalized scroll position.
 * @property {number} viewportFraction Visible fraction of the axis.
 * @property {number} hiddenBefore Hidden fraction before the viewport.
 * @property {number} hiddenAfter Hidden fraction after the viewport.
 */
/**
 * Scroll evidence for both axes.
 * @typedef {object} SceneScrollState
 * @property {SceneScrollAxis} x Horizontal axis evidence.
 * @property {SceneScrollAxis} y Vertical axis evidence.
 */
/**
 * Clipping evidence shared by visual primitives.
 * @typedef {object} SceneClipping
 * @property {boolean} any Whether any edge is clipped.
 * @property {boolean} top Whether the top edge is clipped.
 * @property {boolean} right Whether the right edge is clipped.
 * @property {boolean} bottom Whether the bottom edge is clipped.
 * @property {boolean} left Whether the left edge is clipped.
 * @property {number} visibleWidth Visible width fraction.
 * @property {number} visibleHeight Visible height fraction.
 */
/**
 * Visibility evidence shared by visual primitives.
 * @typedef {object} SceneVisibility
 * @property {boolean} currentlyVisible Whether the element is in view.
 * @property {number} visibleArea Visible fraction of the border box.
 * @property {boolean} scrollReachable Whether scrolling can reveal it.
 * @property {number} effectiveOpacity Composited opacity through ancestors.
 * @property {SceneClipping} clipping Per-edge clipping evidence.
 */
/**
 * Interaction evidence shared by visual primitives.
 * @typedef {object} SceneInteraction
 * @property {boolean} hovered Whether the pointer hovers the element.
 * @property {boolean} focused Whether the element holds focus.
 * @property {boolean} focusWithin Whether a descendant holds focus.
 * @property {string} pointerEvents Computed pointer-events value.
 * @property {string} cursor Computed cursor value.
 */
/**
 * Shared metadata every visual primitive carries.
 * @typedef {object} SceneMeta
 * @property {?string} id Assigned primitive identifier.
 * @property {string} sourceElementId Source element registry identifier.
 * @property {?string} parent Visual parent primitive identifier.
 * @property {SceneRecord} source Source element descriptor.
 * @property {SceneFrame} frame Frame normalized to the capture root.
 * @property {SceneFrame} localFrame Frame normalized to the parent.
 * @property {SceneFrame} visibleFrame Visible frame normalized to the root.
 * @property {SceneVisibility} visibility Visibility evidence.
 * @property {SceneRecord} transform Transform evidence.
 * @property {SceneRecord} layering Stacking and paint-order evidence.
 * @property {SceneInteraction} interaction Interaction evidence.
 */
/**
 * One serialized visual primitive stored in the capture context.
 * @typedef {SceneMeta & {id: string, type: string} & SceneRecord} SceneObject
 */
/**
 * Fixed portion of the resolved capture settings.
 * @typedef {object} SceneSettingsFixed
 * @property {number} opacityThreshold Minimum effective opacity.
 * @property {number} gridColumns Media grid column count.
 * @property {number} gridRows Media grid row count.
 * @property {boolean} includeBinary Include binary descriptors.
 * @property {boolean} includeElementScreenshots Capture element PNGs.
 * @property {boolean} includeComputedStyle Include computed styles.
 * @property {number} elementScreenshotPixelRatio Element PNG pixel ratio.
 * @property {number} elementScreenshotMaxDimension Element PNG size cap.
 * @property {string} elementScreenshotMime Element PNG mime type.
 * @property {number} elementScreenshotQuality Element PNG quality.
 * @property {string} elementScreenshotBackground Element PNG backdrop.
 * @property {number} elementScreenshotConcurrency Element PNG concurrency.
 * @property {boolean} elementScreenshotSkipAutoScale Skip auto scale.
 * @property {boolean} includeOffscreenScrollable Keep scrollable content.
 * @property {boolean} includeRelationships Infer visual relationships.
 * @property {number} maxRasterDimension Maximum raster edge size.
 * @property {boolean} inferSpatialLayouts Infer spatial layouts.
 * @property {number} spatialMaxTracks Maximum inferred tracks per axis.
 * @property {number} spatialTolerance Track alignment tolerance.
 * @property {number} mediaRegionSimilarityContrast Region merge contrast.
 * @property {number} mediaRegionColorDistance Region merge distance.
 * @property {boolean} compactSvgIcons Deduplicate small SVG icons.
 * @property {number} iconMaxWidthFraction Icon width fraction cap.
 * @property {number} iconMaxHeightFraction Icon height fraction cap.
 * @property {number} iconMaxAreaFraction Icon area fraction cap.
 * @property {number} iconGridColumns Icon grid column count.
 * @property {number} iconGridRows Icon grid row count.
 * @property {boolean} includeIconMarkup Include icon markup.
 * @property {boolean} includeIconBinary Include icon raster.
 */
/**
 * Resolved capture settings including caller overrides.
 * @typedef {SceneSettingsFixed & SceneRecord} SceneSettings
 */
/**
 * Per-capture mutable state shared by all primitives.
 * @typedef {object} DescribeContext
 * @property {Element} root Capture boundary element.
 * @property {DOMRectReadOnly} rootRect Root border box.
 * @property {SceneSettings} settings Resolved capture settings.
 * @property {number} nextId Next primitive identifier counter.
 * @property {SceneObject[]} objects Serialized visual primitives.
 * @property {SceneRecord[]} scrollRegions Scrollable region evidence.
 * @property {SceneRecord[]} warnings Diagnostic warnings.
 * @property {WeakMap<Element, string>} elementIds Element id registry.
 * @property {WeakMap<Element, SceneRaster>} rasterCache Raster cache.
 * @property {WeakMap<Element, string[]>} sourceToObjects Primitive ids by source.
 * @property {Map<string, SceneRecord>} elementRegistry Serialized elements.
 * @property {Map<string, Element>} elementsById Live elements by id.
 * @property {Map<string, SceneRecord>} screenshotAssets Screenshot assets.
 * @property {Map<string, SceneRecord>} iconAssets Icon assets.
 */
/**
 * Network Information API members not yet declared by lib.dom.
 * @typedef {object} NetworkInformationLike
 * @property {string} [effectiveType] Effective connection type.
 * @property {number} [downlink] Downlink estimate in Mbps.
 * @property {number} [rtt] Round-trip estimate in ms.
 * @property {boolean} [saveData] Data-saver flag.
 * @property {string} [type] Connection medium.
 */
/**
 * User-Agent Client Hints members not yet declared by lib.dom.
 * @typedef {object} NavigatorUADataLike
 * @property {{brand: string, version: string}[]} [brands] Brand list.
 * @property {boolean} mobile Mobile-device flag.
 * @property {string} platform Platform name.
 * @property {(hints: string[]) => Promise<SceneRecord>} [getHighEntropyValues]
 *   High-entropy value lookup.
 */
/**
 * Navigator members probed here that lib.dom does not yet declare.
 * @typedef {Navigator & {
 *   userAgentData?: NavigatorUADataLike,
 *   connection?: NetworkInformationLike,
 *   mozConnection?: NetworkInformationLike,
 *   webkitConnection?: NetworkInformationLike,
 *   deviceMemory?: number,
 *   globalPrivacyControl?: boolean,
 * }} NavigatorEx
 */
/**
 * Screen members not yet declared by lib.dom.
 * @typedef {Screen & {
 *   availLeft?: number,
 *   availTop?: number,
 *   isExtended?: boolean,
 * }} ScreenEx
 */
/**
 * StorageEstimate members not yet declared by lib.dom.
 * @typedef {StorageEstimate & {usageDetails?: SceneRecord}} StorageEstimateEx
 */
/**
 * One resolved border side used by edge primitives.
 * @typedef {object} SceneBorderSide
 * @property {number} width Border width in CSS pixels.
 * @property {string} style Border style keyword.
 * @property {?SceneRgba} color Parsed border color.
 */
/**
 * Accumulated text line box used while grouping rendered text.
 * @typedef {object} SceneTextLineBox
 * @property {number} top Top edge in CSS pixels.
 * @property {number} bottom Bottom edge in CSS pixels.
 * @property {number} left Left edge in CSS pixels.
 * @property {number} right Right edge in CSS pixels.
 * @property {string} text Accumulated line text.
 */
/**
 * Normalized color descriptor emitted by color evidence helpers.
 * @typedef {object} SceneColorDescriptor
 * @property {SceneRgba} rgba RGBA tuple with a 0-1 alpha channel.
 * @property {string} hex Hexadecimal RGB string.
 * @property {number} luminance Relative luminance.
 */
/**
 * Color statistics sampled from a media raster.
 * @typedef {object} SceneColorStats
 * @property {SceneRecord | null} averageColor Average sampled color.
 * @property {SceneRecord | null} averageContrast Contrast summary record.
 * @property {SceneRecord[][]} grid Sampled color grid.
 * @property {SceneRecord} gridDefinition Grid semantics.
 * @property {SceneRecord | null} gridContrast Adjacent contrast summary.
 * @property {SceneRecord[]} regions Merged color regions.
 * @property {SceneRecord} regionDefinition Region semantics.
 * @property {SceneRecord | null} luminance Luminance distribution.
 * @property {SceneRecord | null} alpha Alpha distribution.
 */
/**
 * One option item inside a selection control.
 * @typedef {object} SceneOptionItem
 * @property {number} index Option index.
 * @property {?string} label Visible option label.
 * @property {?string} value Option value.
 * @property {boolean} selected Whether the option is selected.
 * @property {boolean} disabled Whether the option is disabled.
 * @property {boolean | string} hidden Whether the option is hidden.
 * @property {?string} [group] Optional group label.
 */
/**
 * Normalized corner radii plus aggregate flags.
 * @typedef {object} SceneRadius
 * @property {{x:number,y:number}} topLeft Top-left radius ratios.
 * @property {{x:number,y:number}} topRight Top-right radius ratios.
 * @property {{x:number,y:number}} bottomRight Bottom-right radius ratios.
 * @property {{x:number,y:number}} bottomLeft Bottom-left radius ratios.
 * @property {boolean} rounded Whether any corner is rounded.
 * @property {boolean} uniform Whether all corners are equal.
 */
/**
 * Flattened ancestor backdrop evidence used for compositing.
 * @typedef {object} SceneBackdrop
 * @property {SceneRgba} color Composited flat backdrop color.
 * @property {boolean} exact Whether the backdrop is a flat solid color.
 */
/**
 * Serialized paint-bearing SVG element.
 * @typedef {object} SceneSvgVector
 * @property {string} tag Lower-cased SVG tag name.
 * @property {SceneFrame} frameInSvg Frame normalized to the SVG root.
 * @property {?SceneColorDescriptor} fill Resolved fill color.
 * @property {?SceneColorDescriptor} stroke Resolved stroke color.
 * @property {SceneRecord} paint Computed paint properties.
 * @property {number} strokeWidthRelativeToSvg Stroke width ratio.
 * @property {number[]} strokeDashArrayRelativeToSvg Dash pattern ratios.
 * @property {string} strokeLineCap Stroke line cap.
 * @property {string} strokeLineJoin Stroke line join.
 * @property {number} opacity Effective opacity.
 * @property {?string} text Text content for SVG text nodes.
 */
/**
 * Raster evidence for one visible media element.
 * @typedef {object} SceneRaster
 * @property {HTMLCanvasElement} canvas Sampled raster canvas.
 * @property {SceneRect} visibleRect Visible source rect.
 * @property {string} mime Encoded mime type.
 * @property {?string} binary Encoded raster payload.
 * @property {SceneColorStats} stats Sampled color statistics.
 * @property {string} accuracy Raster fidelity note.
 * @property {SceneRecord} composition Composition evidence.
 */
/**
 * Final transformed border quad for an element.
 * @typedef {object} SceneQuad
 * @property {?string} source Evidence provenance.
 * @property {string} confidence Evidence confidence label.
 * @property {ScenePoint[]} points Normalized quad corners.
 * @property {ScenePoint} center Normalized quad center.
 * @property {number} area Normalized quad area.
 * @property {SceneRecord} edgeLengths Normalized edge lengths.
 * @property {number} orientationDegrees Top-edge orientation in degrees.
 * @property {?number} cornerAngleDegrees Corner angle in degrees.
 */
/**
 * Decomposed CSS transform matrix evidence.
 * @typedef {object} SceneMatrixDescriptor
 * @property {SceneValue} css Original transform value.
 * @property {?SceneRecord} [matrix2d] Normalized 2D matrix terms.
 * @property {boolean} [is2D] Whether the matrix is two-dimensional.
 * @property {?ScenePoint} [scale] Derived scale factors.
 * @property {?number} [rotationDegrees] Derived rotation in degrees.
 * @property {number} [determinant] Normalized 2D determinant.
 * @property {{x:number,y:number,z:number}} [translation] Derived translation.
 * @property {boolean} [parseable] Whether parsing succeeded.
 */
/**
 * Top-layer participation evidence for an element.
 * @typedef {object} SceneTopLayerState
 * @property {boolean} active Whether the element sits in the top layer.
 * @property {boolean} modal Whether the element matches :modal.
 * @property {boolean} popover Whether the element matches :popover-open.
 * @property {boolean} fullscreen Whether the element is fullscreen.
 */
/**
 * CSS paint-phase bucket for modeled stacking order.
 * @typedef {object} ScenePaintPhase
 * @property {number} group Paint phase group index.
 * @property {number} z Stacking-context z coordinate.
 */
/**
 * Hit-test sample point inside an overlap polygon.
 * @typedef {object} SceneHitSample
 * @property {number} x Viewport x coordinate in CSS pixels.
 * @property {number} y Viewport y coordinate in CSS pixels.
 * @property {ScenePoint} normalized Root-normalized sample point.
 */
/**
 * Model-derived visual order for two objects.
 * @typedef {object} SceneModeledOrder
 * @property {SceneObject} top Object painted on top.
 * @property {SceneObject} bottom Object painted underneath.
 * @property {string} reason Basis for the modeled order.
 */
/**
 * Resolved paint-order evidence for an overlapping pair.
 * @typedef {object} SceneVisualOrder
 * @property {?string} topObjectId Identifier of the top object.
 * @property {?string} bottomObjectId Identifier of the bottom object.
 * @property {?string} [topElementRef] Registry ref for the top element.
 * @property {?string} [bottomElementRef] Registry ref for the bottom element.
 * @property {string} confidence Evidence confidence label.
 * @property {string} basis Evidence basis description.
 * @property {number} consensus Hit-test consensus fraction.
 * @property {?string} [hitTestLimitation] Hit-test limitation note.
 * @property {SceneRecord} samples Hit-test sample summary.
 * @property {?SceneRecord} [stackingContextRefs] Stacking context references.
 */
/**
 * Adjacent-cell contrast evidence for a sampled color grid.
 * @typedef {object} SceneGridContrast
 * @property {SceneRecord[][]} grid Per-cell contrast records.
 * @property {?SceneRecord} summary Aggregate contrast summary.
 */
/**
 * Composited raster evidence produced over a flat backdrop.
 * @typedef {object} SceneCompositeRaster
 * @property {HTMLCanvasElement} canvas Composited canvas.
 * @property {?string} binary Encoded composite payload.
 * @property {SceneColorStats} stats Sampled color statistics.
 */
/**
 * Element plus its normalized frame inside a layout container.
 * @typedef {object} SceneLayoutItem
 * @property {Element} element Rendered child element.
 * @property {string} sourceElementId Registered source id.
 * @property {SceneRecord} source Serialized source descriptor.
 * @property {SceneFrame} frame Frame normalized to the container.
 */
/**
 * One inferred grid track on a spatial axis.
 * @typedef {object} SceneTrack
 * @property {number} start Normalized track start.
 * @property {number} end Normalized track end.
 * @property {number} size Normalized track size.
 * @property {number} center Normalized track center.
 */
/**
 * Grid placement indices and labels for one item.
 * @typedef {object} SceneGridPlacement
 * @property {number} columnStart First covered column index.
 * @property {number} columnEnd Last covered column index.
 * @property {number} columnSpan Covered column count.
 * @property {number} rowStart First covered row index.
 * @property {number} rowEnd Last covered row index.
 * @property {number} rowSpan Covered row count.
 * @property {string} horizontal Horizontal placement label.
 * @property {string} vertical Vertical placement label.
 * @property {string} semanticRegion Combined region label.
 */
/**
 * A layout item with its inferred grid placement.
 * @typedef {SceneLayoutItem & {placement: SceneGridPlacement}} ScenePlacement
 */
/**
 * Optional element screenshot capture settings.
 * @typedef {object} SceneElementCaptureOptions
 * @property {string} [mime] Encoded mime type.
 * @property {number} [quality] Encoding quality.
 * @property {number} [pixelRatio] Raster pixel ratio.
 * @property {number} [maxDimension] Maximum raster edge.
 * @property {string} [background] Backdrop selector.
 * @property {boolean} [fresh] Bypass the capture cache.
 * @property {boolean} [skipAutoScale] Skip automatic scaling.
 */
/**
 * Color input accepted by contrast helpers: tuple or descriptor record.
 * @typedef {SceneRgba | SceneColorDescriptor | null} SceneColorLike
 */
/**
 * Object form of describe() options: capture settings plus callbacks.
 * @typedef {Partial<SceneSettingsFixed> & SceneRecord & {
 *   onComplete?: Function,
 *   requestId?: string | number,
 * }} DescribeOptionsObject
 */
/**
 * Accepted forms of the describe() options argument.
 * @typedef {DescribeOptionsObject | Function | string | number | null}
 *   DescribeOptions
 */
/**
 * Rolling-capture encoder quality preset.
 * @typedef {object} RollingQuality
 * @property {number} fps Target frames per second.
 * @property {number} videoBitsPerSecond Target video bitrate.
 */
/**
 * Resolved rolling-capture recorder configuration.
 * @typedef {object} RollingConfig
 * @property {?string} target Last supplied target selector reference.
 * @property {number} window Rolling buffer window in milliseconds.
 * @property {number} segmentDuration MediaRecorder segment duration.
 * @property {string|RollingQuality} quality Preset name or overrides.
 * @property {?number} fps Optional frames-per-second override.
 * @property {?number} videoBitsPerSecond Optional video bitrate override.
 * @property {?number} audioBitsPerSecond Optional audio bitrate.
 * @property {boolean} audio Whether audio tracks are retained.
 * @property {readonly string[]} mimeTypes Preferred recorder MIME candidates.
 * @property {number} transferChunkSize Byte budget per transferred chunk.
 * @property {string} eventPrefix Prefix used for global evidence events.
 * @property {number} maxBufferBytes Rolling buffer byte ceiling.
 * @property {number} maxCompletedBytes Completed result byte ceiling.
 * @property {number} maxCaptures Completed result count ceiling.
 * @property {boolean} autoRemoveAfterTransfer Whether transfers delete results.
 */
/**
 * Options accepted by RollingCapture construction and set().
 * @typedef {object} RollingOptions
 * @property {string|Element} [target] Selector or element to record.
 * @property {number} [window] Rolling buffer window in milliseconds.
 * @property {number} [segmentDuration] MediaRecorder segment duration.
 * @property {string|RollingQuality} [quality] Preset name or overrides.
 * @property {?number} [fps] Optional frames-per-second override.
 * @property {?number} [videoBitsPerSecond] Optional video bitrate override.
 * @property {?number} [audioBitsPerSecond] Optional audio bitrate.
 * @property {boolean} [audio] Whether audio tracks are retained.
 * @property {string[]} [mimeTypes] Preferred recorder MIME candidates.
 * @property {number} [transferChunkSize] Byte budget per transferred chunk.
 * @property {string} [eventPrefix] Prefix used for global evidence events.
 * @property {number} [maxBufferBytes] Rolling buffer byte ceiling.
 * @property {number} [maxCompletedBytes] Completed result byte ceiling.
 * @property {number} [maxCaptures] Completed result count ceiling.
 * @property {boolean} [autoRemoveAfterTransfer] Whether transfers delete results.
 */
/**
 * Options that start a buffered video capture.
 * @typedef {object} RollingStartOptions
 * @property {number} [before] Milliseconds of buffered video to keep.
 * @property {number} [duration] Milliseconds to record after the trigger.
 * @property {string} [id] Caller-assigned capture identifier.
 * @property {unknown} [metadata] Opaque metadata echoed in results.
 */
/**
 * Options that stop a capture early.
 * @typedef {object} RollingStopOptions
 * @property {string} [reason] Stop reason recorded on the result.
 * @property {?number} [at] Explicit end timestamp override.
 */
/**
 * Options that control disarm teardown.
 * @typedef {object} RollingDisarmOptions
 * @property {boolean} [clear] Whether buffered segments are discarded.
 * @property {boolean} [force] Whether active captures are force-stopped.
 */
/**
 * Element surface exposing captureStream(), normally canvas or video.
 * @typedef {object} RollingCaptureSurface
 * @property {(fps?: number) => MediaStream} [captureStream] Standard hook.
 * @property {(fps?: number) => MediaStream} [webkitCaptureStream] WebKit hook.
 */
/**
 * In-flight MediaRecorder rotation segment.
 * @typedef {object} RollingSegment
 * @property {MediaRecorder} recorder Active segment recorder.
 * @property {Blob[]} chunks Data chunks collected for this segment.
 * @property {number} start Wall-clock start timestamp.
 * @property {Promise<RollingSegmentResult>} done Resolves once stopped.
 */
/**
 * Completed buffered video segment.
 * @typedef {object} RollingSegmentResult
 * @property {number} start Wall-clock start timestamp.
 * @property {number} end Wall-clock end timestamp.
 * @property {number} duration Segment duration in milliseconds.
 * @property {string} mimeType Container MIME type.
 * @property {Blob} blob Encoded segment media.
 */
/**
 * In-flight capture request tracked while it completes.
 * @typedef {object} RollingCaptureTask
 * @property {string} id Capture identifier.
 * @property {string} kind Capture kind.
 * @property {number} trigger Wall-clock trigger timestamp.
 * @property {number} requestedStart Requested interval start.
 * @property {?number} requestedEnd Requested interval end once known.
 * @property {number} before Requested lookback duration.
 * @property {number} duration Requested record duration.
 * @property {unknown} metadata Opaque metadata echoed in results.
 * @property {number|ReturnType<typeof setTimeout>} timer Auto-stop handle.
 * @property {boolean} stopping Whether stop() already began.
 * @property {Promise<unknown>} done Promise resolved with the result.
 * @property {(value: unknown) => void} resolve Result resolver.
 * @property {(reason?: unknown) => void} reject Result rejecter.
 */
/**
 * Completed buffered video evidence.
 * @typedef {object} RollingVideoResult
 * @property {string} id Capture identifier.
 * @property {string} kind Result kind.
 * @property {number} trigger Wall-clock trigger timestamp.
 * @property {number} requestedStart Requested interval start.
 * @property {?number} requestedEnd Requested interval end.
 * @property {number} actualStart Delivered interval start.
 * @property {number} actualEnd Delivered interval end.
 * @property {number} requestedBefore Requested lookback duration.
 * @property {number} actualBefore Delivered lookback duration.
 * @property {number} missingBefore Lookback the buffer could not supply.
 * @property {number} sourceStart First segment start timestamp.
 * @property {number} sourceEnd Last segment end timestamp.
 * @property {number} trimStart Milliseconds trimmed from the first segment.
 * @property {number} trimDuration Delivered duration.
 * @property {string} reason Stop reason.
 * @property {unknown} metadata Opaque metadata echoed in results.
 * @property {string} mimeType Container MIME type.
 * @property {boolean} audio Whether audio tracks are present.
 * @property {number} size Total encoded byte count.
 * @property {RollingSegmentResult[]} segments Source segments.
 */
/**
 * Completed still-image evidence.
 * @typedef {object} RollingImageResult
 * @property {string} id Capture identifier.
 * @property {string} kind Result kind.
 * @property {number} createdAt Wall-clock capture timestamp.
 * @property {number} width Pixel width.
 * @property {number} height Pixel height.
 * @property {string} mimeType Encoded image MIME type.
 * @property {number} size Encoded byte count.
 * @property {number} quality Encoder quality used.
 * @property {number} scale Raster scale used.
 * @property {unknown} metadata Opaque metadata echoed in results.
 * @property {Blob} blob Encoded image data.
 */
/**
 * Rasterization options shared by snapshot helpers.
 * @typedef {object} RollingDrawOptions
 * @property {string} type Encoded image MIME type.
 * @property {number} quality Encoder quality.
 * @property {number} scale Raster scale.
 * @property {string} background Backdrop fill or "transparent".
 */
/**
 * Options accepted by RollingCapture.snapshot().
 * @typedef {object} RollingSnapshotOptions
 * @property {?Element|string} [target] Element or selector to capture.
 * @property {string} [type] Encoded image MIME type.
 * @property {number} [quality] Encoder quality.
 * @property {number} [scale] Raster scale.
 * @property {string} [id] Caller-assigned capture identifier.
 * @property {unknown} [metadata] Opaque metadata echoed in results.
 * @property {string} [background] Backdrop fill or "transparent".
 */
/**
 * Options accepted by transfer() implementations.
 * @typedef {object} RollingTransferOptions
 * @property {string} [sink] Global sink property name.
 * @property {number} [chunkSize] Byte budget per transferred chunk.
 */
/**
 * Sink that receives streamed transfer payloads.
 * @typedef {(payload: Record<string, unknown>) => Promise<unknown>}
 *   EvidenceSink
 */
/**
 * Timeline marker or diagnostic entry.
 * @typedef {object} EvidenceTimelineEntry
 * @property {number} time Wall-clock entry timestamp.
 * @property {string} type Entry type tag.
 * @property {unknown} data Entry payload.
 * @property {string} url Document URL when recorded.
 */
/**
 * Stored description evidence bundle.
 * @typedef {object} DescriptionResult
 * @property {string} id Capture identifier.
 * @property {string} kind Result kind.
 * @property {number} createdAt Wall-clock capture timestamp.
 * @property {unknown} metadata Opaque metadata echoed in results.
 * @property {SceneRecord} manifest Serialized scene manifest.
 * @property {Map<string, Blob>} files Externalized binary assets.
 * @property {number} manifestBytes JSON manifest byte count.
 * @property {number} binaryBytes Total binary asset byte count.
 */
/**
 * EvidenceRuntime construction options.
 * @typedef {object} EvidenceOptions
 * @property {string|Element} [target] Selector or element to record.
 * @property {boolean} [diagnostics] Whether diagnostics start automatically.
 * @property {number} [maxTimelineEntries] Timeline entry ceiling.
 * @property {number} [maxDescriptions] Stored description ceiling.
 * @property {number} [maxDescriptionBytes] Stored description byte ceiling.
 * @property {string} [eventPrefix] Prefix used for global evidence events.
 * @property {boolean} [autoArm] Whether create() arms the recorder.
 */
/**
 * Resolved EvidenceRuntime configuration.
 * @typedef {object} EvidenceConfig
 * @property {string|Element|null} target Configured evidence target.
 * @property {boolean} diagnostics Whether diagnostics run.
 * @property {number} maxTimelineEntries Timeline entry ceiling.
 * @property {number} maxDescriptions Stored description ceiling.
 * @property {number} maxDescriptionBytes Stored description byte ceiling.
 * @property {string} eventPrefix Prefix used for global evidence events.
 * @property {boolean} [autoArm] Whether create() arms the recorder.
 */
/**
 * Options accepted by EvidenceRuntime.description().
 * @typedef {object} EvidenceDescriptionOptions
 * @property {string|Element|null} [target] Element or selector to describe.
 * @property {string} [id] Caller-assigned capture identifier.
 * @property {unknown} [metadata] Opaque metadata echoed in results.
 * @property {DescribeOptions} [options] describe() configuration.
 * @property {boolean} [externalizeBinary] Whether binary assets split out.
 */
/**
 * Options accepted by EvidenceRuntime.evidence().
 * @typedef {object} EvidenceRequestOptions
 * @property {readonly string[]} [modes] Evidence modes to produce.
 * @property {number} [before] Milliseconds of buffered video to keep.
 * @property {number} [duration] Milliseconds to record after the trigger.
 * @property {string|Element|null} [target] Element or selector to capture.
 * @property {unknown} [metadata] Opaque metadata echoed in results.
 * @property {RollingSnapshotOptions} [capture] Still-capture options.
 * @property {EvidenceDescriptionOptions} [description] Description options.
 */
/**
 * Combined evidence() result.
 * @typedef {object} EvidenceBundle
 * @property {unknown} [video] Buffered video result when requested.
 * @property {unknown} [capture] Still-capture result when requested.
 * @property {unknown} [description] Description result when requested.
 * @property {EvidenceTimelineEntry[]} [markers] Timeline markers.
 * @property {EvidenceTimelineEntry[]} [diagnostics] Diagnostics entries.
 */
/**
 * Diagnostic feed toggles.
 * @typedef {object} EvidenceDiagnosticOptions
 * @property {boolean} [errors] Window error and rejection capture.
 * @property {boolean} [mutations] DOM mutation summaries.
 * @property {boolean} [viewport] Viewport resize capture.
 * @property {boolean} [performance] PerformanceObserver entries.
 */
/**
 * Browser-side rendered scene descriptor for visual agents.
 *
 * Design rules:
 * - Only the reference/root element uses absolute CSS-pixel dimensions.
 * - Every descendant measurement is normalized to a ratio.
 * - Hidden/non-rendered nodes are omitted.
 * - Scrollable but currently off-screen rendered content is retained and
 *   explicitly marked as not currently visible / scroll-reachable.
 * - DOM/CSS are treated as evidence. Output primitives describe what a user
 *   perceives: text, media, surfaces, contours, separators, shadows, controls.
 * - Media includes its current visible crop as PNG plus an average-colour grid.
 * - Every grid cell includes local contrast to adjacent cells, the media-wide
 *   average, and the resolved flat backdrop when available.
 * - Contrast is sampled against the best background available from the actual
 *   hit-test stack, using media raster samples when possible.
 * - Exactness/confidence fields distinguish browser-observable facts from
 *   approximations (notably complex CSS blending/backdrop filtering).
 */
/**
 * Provide Descriptor scene-evidence operations.
 *
 * @class Descriptor
 */
class Descriptor {
  /** @type {WeakMap<Element, SceneRecord>} */
  static #screenshotCache = new WeakMap();
  /** @type {Promise<SceneRecord> | null} */
  static #clientMetadataCache = null;
  /**
   * Capture a normalized visual scene from a rendered root subtree.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} root Root element defining the capture or lookup boundary.
   * @param {DescribeOptions} [options] Configuration for this operation; omitted fields use its declared defaults.
   * @param {?Function} [callback] Optional completion callback invoked by the operation.
   * @returns {Promise<SceneRecord>} Captured describe evidence for the calling operation.
   */
  static describe = async (root, options = {}, callback = null) => {
    if (!(root instanceof Element))
      throw new TypeError("root must be an Element.");
    const startedAt = performance.now();
    const {
      onComplete = callback,
      requestId = null,
      ...configuration
    } = /** @type {DescribeOptionsObject} */ (
      typeof options === "function"
        ? {
            onComplete: options,
          }
        : ["string", "number"].includes(typeof options)
          ? {
              requestId: options,
            }
          : (options ?? {})
    );
    if (onComplete !== null && typeof onComplete !== "function")
      throw new TypeError("callback must be a function or null.");
    if (requestId !== null && !["string", "number"].includes(typeof requestId))
      throw new TypeError("requestId must be a string, number or null.");
    this.#selectorCache = new WeakMap();
    const settings = /** @type {SceneSettings} */ ({
      opacityThreshold: 0.001,
      gridColumns: 4,
      gridRows: 4,
      includeBinary: true,
      includeElementScreenshots: false,
      includeComputedStyle: false,
      elementScreenshotPixelRatio: 1,
      elementScreenshotMaxDimension: 1600,
      elementScreenshotMime: "image/png",
      elementScreenshotQuality: 0.92,
      elementScreenshotBackground: "transparent",
      elementScreenshotConcurrency: 4,
      elementScreenshotSkipAutoScale: false,
      includeOffscreenScrollable: true,
      includeRelationships: true,
      maxRasterDimension: 4096,
      inferSpatialLayouts: true,
      spatialMaxTracks: 8,
      spatialTolerance: 0.035,
      mediaRegionSimilarityContrast: 1.35,
      mediaRegionColorDistance: 0.22,
      compactSvgIcons: true,
      iconMaxWidthFraction: 0.14,
      iconMaxHeightFraction: 0.14,
      iconMaxAreaFraction: 0.0125,
      iconGridColumns: 3,
      iconGridRows: 3,
      includeIconMarkup: true,
      includeIconBinary: false,
      ...configuration,
    });
    const rootRect = root.getBoundingClientRect();
    if (rootRect.width <= 0 || rootRect.height <= 0)
      throw new RangeError("root must have a rendered size.");
    const context = /** @type {DescribeContext} */ ({
      root,
      rootRect,
      settings,
      nextId: 1,
      objects: [],
      scrollRegions: [],
      warnings: [],
      elementIds: new WeakMap(),
      rasterCache: new WeakMap(),
      sourceToObjects: new WeakMap(),
      elementRegistry: new Map(),
      elementsById: new Map(),
      screenshotAssets: new Map(),
      iconAssets: new Map(),
    });
    await this.#walk(root, null, context);
    if (settings.includeElementScreenshots)
      await this.#captureElementScreenshots(context);
    this.#resolveTextContrast(context);
    this.#resolveVisualContrast(context);
    this.#resolveControlContrast(context);
    this.#resolvePerception(context);
    const relationships = settings.includeRelationships
      ? this.#relationships(context)
      : [];
    const producedAt = new Date();
    const scene = {
      metadata: {
        requestId,
        producedAt: producedAt.toISOString(),
        producedAtLocal: producedAt.toString(),
        producedAtEpochMs: producedAt.getTime(),
        page: {
          url: this.#urlMetadata(location.href),
          baseUrl: this.#urlMetadata(document.baseURI),
          title: document.title || null,
          referrer: document.referrer
            ? this.#urlMetadata(document.referrer)
            : null,
          language: document.documentElement.lang || navigator.language || null,
          characterSet: document.characterSet || null,
          contentType: document.contentType || null,
          compatMode: document.compatMode || null,
        },
        client: await this.#clientMetadata(),
        screen: {
          width: screen.width,
          height: screen.height,
          availableWidth: screen.availWidth,
          availableHeight: screen.availHeight,
          availableLeft:
            /** @type {ScreenEx} */
            (screen).availLeft ?? null,
          availableTop: /** @type {ScreenEx} */ (screen).availTop ?? null,
          colorDepth: screen.colorDepth,
          pixelDepth: screen.pixelDepth,
          isExtended: /** @type {ScreenEx} */ (screen).isExtended ?? null,
          orientation: screen.orientation
            ? {
                type: screen.orientation.type,
                angle: screen.orientation.angle,
              }
            : null,
        },
        window: {
          width: innerWidth,
          height: innerHeight,
          outerWidth,
          outerHeight,
          screenX: globalThis.screenX,
          screenY: globalThis.screenY,
          scrollX: this.#round(scrollX),
          scrollY: this.#round(scrollY),
          devicePixelRatio,
        },
        visualViewport: globalThis.visualViewport
          ? {
              width: this.#round(globalThis.visualViewport.width),
              height: this.#round(globalThis.visualViewport.height),
              offsetX: this.#round(globalThis.visualViewport.offsetLeft),
              offsetY: this.#round(globalThis.visualViewport.offsetTop),
              pageX: this.#round(globalThis.visualViewport.pageLeft),
              pageY: this.#round(globalThis.visualViewport.pageTop),
              scale: this.#round(globalThis.visualViewport.scale),
            }
          : null,
        document: {
          readyState: document.readyState,
          visibilityState: document.visibilityState,
          fullscreen: Boolean(document.fullscreenElement),
          pictureInPicture: Boolean(document.pictureInPictureElement),
        },
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
        locale: Intl.DateTimeFormat().resolvedOptions().locale || null,
        coordinateUnits: "CSS pixels",
        counts: {
          elements: context.elementRegistry.size,
          objects: context.objects.length,
          icons: context.iconAssets.size,
          screenshots: context.screenshotAssets.size,
          scrollRegions: context.scrollRegions.length,
          relationships: relationships.length,
        },
        executionMs: 0,
      },
      reference: {
        tag: root.tagName.toLowerCase(),
        id: root.id || null,
        width: this.#round(rootRect.width),
        height: this.#round(rootRect.height),
        sourceElementId: this.#elementId(root, context),
        selector: this.#selectElement(root),
        viewportFrame: {
          x: this.#round(rootRect.left),
          y: this.#round(rootRect.top),
          right: this.#round(rootRect.right),
          bottom: this.#round(rootRect.bottom),
          width: this.#round(rootRect.width),
          height: this.#round(rootRect.height),
        },
        documentFrame: {
          x: this.#round(rootRect.left + scrollX),
          y: this.#round(rootRect.top + scrollY),
          right: this.#round(rootRect.right + scrollX),
          bottom: this.#round(rootRect.bottom + scrollY),
          width: this.#round(rootRect.width),
          height: this.#round(rootRect.height),
        },
      },
      viewport: {
        width: this.#ratio(rootRect.width, innerWidth),
        height: this.#ratio(rootRect.height, innerHeight),
      },
      scroll: this.#scrollState(root),
      objects: context.objects.map(({ transform, layering, ...object }) => ({
        ...object,
        elementVisualRef: object.sourceElementId,
        paintLayer: layering?.[String("localPaintLayer")] ?? null,
      })),
      elements: Object.fromEntries(context.elementRegistry),
      assets: {
        icons: [...context.iconAssets.values()],
        screenshots: [...context.screenshotAssets.values()],
      },
      scrollRegions: context.scrollRegions,
      spatialLayouts: settings.inferSpatialLayouts
        ? this.#inferSpatialLayouts(context)
        : [],
      visualStack: this.#visualStack(context, relationships),
      relationships,
      diagnostics: {
        warnings: context.warnings,
        guarantees: {
          geometry: "browser-layout",
          textLineBreaks: "range-client-rects",
          imageCrop: "rasterized-visible-media",
          svgCrop: "serialized-svg-rasterization",
          mediaColorGrid: "sampled-final-media-raster",
          compactSvgIcons: "deduplicated-asset-plus-instance",
          roundedGeometry: "computed-border-radius-normalized-per-axis",
          strokePatterns: "css-border-semantics-and-svg-dasharray",
          semanticControls: "native-html-plus-aria-widget-state",
          accessibleNames:
            "aria-label-labelledby-native-labels-and-visible-text",
          domElementRegistry:
            "deduplicated-selector-html-attributes-dataset-properties-role-name-value-state-form-structure",
          elementScreenshots:
            "html-to-image-rendered-png-assets-deduplicated-per-source-element",
          binaryStorage:
            "sha256-content-addressed-external-files-referenced-from-json-manifest",
          flatBackgroundContrast: "sampled-or-alpha-composited",
          wcag22Contrast: "standards-thresholds-with-unrounded-pass-comparison",
          perceptualSalience:
            "explicit-non-normative-size-contrast-geometry-heuristic",
          inferredSpatialLayout:
            "rendered-coordinate-density-and-alignment-analysis-independent-of-css-layout-mode",
          mediaColorRegions:
            "adjacent-grid-cell-clustering-with-local-boundary-contrast",
          transformedGeometry:
            "final-browser-painted-border-quad-when-getBoxQuads-is-available-with-axis-aligned-fallback",
          visualStacking:
            "css-stacking-context-model-plus-multipoint-browser-hit-test-consensus-for-overlaps",
          absoluteGeometry:
            "viewport-and-document-css-pixel-frames-per-registered-element",
          canvasAnalysis:
            "intrinsic-bitmap-css-size-pixel-density-and-visible-raster-color-analysis",
          svgPaintResolution:
            "computed-svg-paint-with-currentcolor-resolved-before-serialization-including-fill-stroke-and-color-bearing-paint-properties",
        },
        limitations: [
          "Arbitrary CSS mix-blend-mode is exact only when the sampled backdrop is available; otherwise it is marked approximate.",
          "backdrop-filter cannot be read back as final page pixels through standard DOM APIs and is reported with reduced confidence.",
          "CSS masks, complex clip-path shapes, 3D transforms, and external SVG/CSS resources can reduce raster exactness.",
          "The browser exposes final transformed border quadrilaterals but not a complete public display-list API; overlap paint order therefore combines stacking-context analysis with multi-point elementsFromPoint consensus.",
          "Occlusion uses geometric intersection plus sampled paint order; transparent holes in arbitrary DOM surfaces are not pixel-perfect without page screenshot access.",
          "Browser privacy rules do not expose reliable visited-link state, so links describe destination semantics but never claim :visited state.",
          "Perceptual salience is a descriptor heuristic, not a WCAG conformance rule; it intentionally combines normalized size, contrast, thickness, and visible exposure.",
          "Inferred spatial grids describe rendered alignment and density and can differ from author-declared CSS layout intent.",
        ],
      },
    };
    /** @type {SceneRecord} */
    const sceneMetadata = /** @type {SceneRecord} */ (scene.metadata);
    sceneMetadata[String("executionMs")] = this.#round(
      performance.now() - startedAt,
      3,
    );
    await onComplete?.(scene, JSON.stringify(scene));
    return scene;
  };
  /**
   * Describe URL components without navigating or fetching the destination.
   * @param {string} value Value read from the current DOM, configuration or serialized scene.
   * @returns {SceneRecord} Captured urlMetadata evidence for the calling operation.
   */
  static #urlMetadata = value => {
    const url = new URL(value, document.baseURI);
    return {
      full: url.href,
      origin: url.origin,
      protocol: url.protocol,
      scheme: url.protocol.slice(0, -1),
      host: url.host,
      hostname: url.hostname,
      port: url.port || null,
      pathname: url.pathname,
      pathSegments: url.pathname.split("/").filter(Boolean),
      search: url.search || null,
      query: {
        entries: [...url.searchParams.entries()],
        parameters: Object.fromEntries(
          [...new Set(url.searchParams.keys())].map(key => [
            key,
            url.searchParams.getAll(key).length === 1
              ? url.searchParams.get(key)
              : url.searchParams.getAll(key),
          ]),
        ),
      },
      hash: url.hash || null,
      hashValue: url.hash ? url.hash.slice(1) : null,
      credentialsPresent: Boolean(url.username || url.password),
    };
  };
  /**
   * Cache one asynchronous snapshot of browser capabilities and preferences.
   * @returns {Promise<SceneRecord>} Captured clientMetadata evidence for the calling operation.
   */
  static #clientMetadata = () => {
    this.#clientMetadataCache ??= (async () => {
      const userAgent = navigator.userAgent;
      /** @type {SceneRecord | null} */
      let userAgentData = null;
      try {
        const data = /** @type {NavigatorEx} */ (navigator).userAgentData;
        userAgentData = data
          ? {
              brands: data.brands ?? [],
              mobile: data.mobile,
              platform: data.platform,
              highEntropy: data.getHighEntropyValues
                ? await data.getHighEntropyValues([
                    "architecture",
                    "bitness",
                    "formFactors",
                    "fullVersionList",
                    "model",
                    "platformVersion",
                    "uaFullVersion",
                    "wow64",
                  ])
                : null,
            }
          : null;
      } catch {
        // High-entropy client hints may be denied; retain null metadata.
      }
      /** @type {StorageEstimateEx | null} */
      let storage = null;
      try {
        storage = navigator.storage?.estimate
          ? await navigator.storage.estimate()
          : null;
      } catch {
        // Storage estimates may be blocked; retain null metadata.
      }
      const navigatorEx = /** @type {NavigatorEx} */ (navigator);
      const connection =
        navigatorEx.connection ??
        navigatorEx.mozConnection ??
        navigatorEx.webkitConnection;
      return {
        browser: {
          name: /(?:Edg|EdgiOS|EdgA)\//.test(userAgent)
            ? "Edge"
            : /(?:OPR|Opera)\//.test(userAgent)
              ? "Opera"
              : /(?:Chrome|CriOS)\//.test(userAgent)
                ? "Chrome"
                : /(?:Firefox|FxiOS)\//.test(userAgent)
                  ? "Firefox"
                  : /Safari\//.test(userAgent)
                    ? "Safari"
                    : null,
          version:
            (userAgent.match(/(?:Edg|EdgiOS|EdgA)\/([\d.]+)/) ??
              userAgent.match(/(?:OPR|Opera)\/([\d.]+)/) ??
              userAgent.match(/(?:Chrome|CriOS)\/([\d.]+)/) ??
              userAgent.match(/(?:Firefox|FxiOS)\/([\d.]+)/) ??
              userAgent.match(/Version\/([\d.]+).*Safari/))?.[1] ?? null,
          vendor: navigator.vendor || null,
          userAgent,
          appVersion: navigator.appVersion || null,
        },
        os: {
          name:
            /(?:iPhone|iPad|iPod)/.test(userAgent) ||
            /Macintosh/.test(userAgent) && (navigator.maxTouchPoints ?? 0) > 1
              ? "iOS/iPadOS"
              : /Macintosh|Mac OS X/.test(userAgent)
                ? "macOS"
                : /Windows/.test(userAgent)
                  ? "Windows"
                  : /Android/.test(userAgent)
                    ? "Android"
                    : /CrOS/.test(userAgent)
                      ? "ChromeOS"
                      : /Linux/.test(userAgent)
                        ? "Linux"
                        : null,
          version:
            (userAgent.match(/(?:CPU (?:iPhone )?OS|iPhone OS) ([\d_]+)/) ??
              userAgent.match(/Mac OS X ([\d_]+)/) ??
              userAgent.match(/Windows NT ([\d.]+)/) ??
              userAgent.match(/Android ([\d.]+)/) ??
              userAgent.match(/CrOS [^ ]+ ([\d.]+)/))?.[1]?.replaceAll(
              "_",
              ".",
            ) ?? null,
          platform: navigator.platform || null,
        },
        device: {
          mobile:
            userAgentData?.[String("mobile")] ??
            /Mobile|Android|iPhone|iPad|iPod/i.test(userAgent),
          hardwareConcurrency: navigator.hardwareConcurrency ?? null,
          deviceMemoryGiB: navigatorEx.deviceMemory ?? null,
          maxTouchPoints: navigator.maxTouchPoints ?? 0,
          touchCapable: (navigator.maxTouchPoints ?? 0) > 0,
        },
        navigator: {
          language: navigator.language || null,
          languages: [...(navigator.languages ?? [])],
          cookieEnabled: navigator.cookieEnabled,
          online: navigator.onLine,
          doNotTrack: navigator.doNotTrack ?? null,
          globalPrivacyControl: navigatorEx.globalPrivacyControl ?? null,
          webdriver: navigator.webdriver,
          pdfViewerEnabled: navigator.pdfViewerEnabled ?? null,
        },
        preferences: {
          colorScheme: matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : matchMedia("(prefers-color-scheme: light)").matches
              ? "light"
              : "no-preference",
          reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
          forcedColors: matchMedia("(forced-colors: active)").matches,
          contrastMore: matchMedia("(prefers-contrast: more)").matches,
          hover: matchMedia("(hover: hover)").matches,
          anyHover: matchMedia("(any-hover: hover)").matches,
          pointer: matchMedia("(pointer: fine)").matches
            ? "fine"
            : matchMedia("(pointer: coarse)").matches
              ? "coarse"
              : "none",
          anyPointerFine: matchMedia("(any-pointer: fine)").matches,
          colorGamut: matchMedia("(color-gamut: rec2020)").matches
            ? "rec2020"
            : matchMedia("(color-gamut: p3)").matches
              ? "p3"
              : matchMedia("(color-gamut: srgb)").matches
                ? "srgb"
                : null,
          dynamicRangeHigh: matchMedia("(dynamic-range: high)").matches,
        },
        network: connection
          ? {
              effectiveType: connection.effectiveType ?? null,
              downlinkMbps: connection.downlink ?? null,
              rttMs: connection.rtt ?? null,
              saveData: connection.saveData ?? null,
              type: connection.type ?? null,
            }
          : null,
        storage: storage
          ? {
              quotaBytes: storage.quota ?? null,
              usageBytes: storage.usage ?? null,
              usageDetails: storage.usageDetails ?? null,
            }
          : null,
        userAgentData,
      };
    })();
    return this.#clientMetadataCache;
  };
  /**
   * Visit rendered descendants and append their visual primitives to the capture context.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {?string} visualParentId Visualparentid used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {Promise<void>} Updates the capture context in place.
   */
  static #walk = async (element, visualParentId, context) => {
    if (!this.#isRendered(element, context.settings.opacityThreshold)) return;
    const rect = element.getBoundingClientRect();
    const visibleRect = this.#visibleRect(element, rect, context.rootRect);
    let scrollAncestor = element.parentElement;
    while (scrollAncestor) {
      const state = this.#scrollState(scrollAncestor);
      if (state.x.scrollable || state.y.scrollable) break;
      if (scrollAncestor === context.root) {
        scrollAncestor = null;
        break;
      }
      scrollAncestor = scrollAncestor.parentElement;
    }
    if (
      !(visibleRect.width > 0 && visibleRect.height > 0) &&
      !context.settings.includeOffscreenScrollable &&
      scrollAncestor
    )
      return;
    const elementId = this.#elementId(element, context);
    this.#registerElement(element, context);
    const style = getComputedStyle(element);
    const meta = this.#baseMeta(
      element,
      rect,
      visibleRect,
      visualParentId,
      scrollAncestor,
      context,
    );
    /** @type {SceneObject[]} */
    const created = [];
    const compactIcon =
      element instanceof SVGSVGElement &&
      context.settings.compactSvgIcons &&
      this.#isSvgIcon(element, rect, context);
    const surface = this.#surfacePrimitive(element, style, meta, context);
    if (surface) created.push(surface);
    if (compactIcon) {
      const icon = await this.#iconPrimitive(element, style, meta, context);
      if (icon) created.push(icon);
    } else {
      const media = await this.#mediaPrimitive(element, style, meta, context);
      if (media) created.push(media);
      if (element instanceof SVGSVGElement)
        created.push(this.#svgPrimitive(element, style, meta, media));
    }
    const text = compactIcon
      ? null
      : this.#textPrimitive(element, style, meta, context);
    if (text) created.push(text);
    created.push(...this.#edgePrimitives(element, style, meta, context));
    if (style.boxShadow !== "none" || style.textShadow !== "none")
      created.push({
        ...meta,
        id: `${meta.sourceElementId}-shadow`,
        type: "shadow",
        boxShadow: style.boxShadow === "none" ? null : style.boxShadow,
        textShadow: style.textShadow === "none" ? null : style.textShadow,
        paintConfidence: "computed-style",
      });
    const control = this.#controlPrimitive(element, style, meta);
    if (control) created.push(control);
    created.push(...this.#pseudoPrimitives(element, meta, context));
    for (const object of created) {
      object.layering = {
        ...object.layering,
        localPaintLayer: this.#localPaintLayer(
          object.type,
          /** @type {?string} */
          (object[String("sourceKind")]),
        ),
      };
      context.objects.push(object);
      const sourceObjects = context.sourceToObjects.get(element) ?? [];
      sourceObjects.push(object.id);
      context.sourceToObjects.set(element, sourceObjects);
    }
    const nextVisualParentId =
      created.find(item =>
        ["surface", "control", "image", "svg", "icon"].includes(item.type),
      )?.id ?? visualParentId;
    const scrollState = this.#scrollState(element);
    if (scrollState.x.scrollable || scrollState.y.scrollable)
      context.scrollRegions.push({
        id: `scroll-${elementId}`,
        sourceElementId: elementId,
        source: meta.source,
        frame: meta.frame,
        visibleFrame: meta.visibleFrame,
        state: scrollState,
        contentExtent: {
          width: this.#ratio(
            element.scrollWidth,
            Math.max(1, element.clientWidth),
          ),
          height: this.#ratio(
            element.scrollHeight,
            Math.max(1, element.clientHeight),
          ),
        },
        hiddenContent: {
          left: scrollState.x.position,
          right: this.#round(1 - scrollState.x.position),
          top: scrollState.y.position,
          bottom: this.#round(1 - scrollState.y.position),
        },
      });
    /* SVG internals are already represented by the vector/icon primitive.
     * Walking paths, groups and uses separately creates substantial JSON noise.
     */
    if (element instanceof SVGSVGElement) return;
    await Promise.all(
      [...element.children].map(child =>
        this.#walk(child, nextVisualParentId, context),
      ),
    );
  };
  /**
   * Build shared source, frame and parent metadata for one visual primitive.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {SceneRect} visibleRect Visiblerect used by this operation.
   * @param {?string} visualParentId Visualparentid used by this operation.
   * @param {?Element} scrollAncestor Scrollancestor used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneMeta} Captured baseMeta evidence for the calling operation.
   */
  static #baseMeta = (
    element,
    rect,
    visibleRect,
    visualParentId,
    scrollAncestor,
    context,
  ) => {
    const rootRect = context.rootRect;
    const parentRect =
      element.parentElement?.getBoundingClientRect() ?? rootRect;
    const style = getComputedStyle(element);
    const elementId = this.#elementId(element, context);
    const elementVisual = /** @type {SceneRecord | undefined} */ (
      context.elementRegistry.get(elementId)?.[String("visual")]
    );
    const visibleArea =
      rect.width && rect.height
        ? (visibleRect.width * visibleRect.height) / (rect.width * rect.height)
        : 0;
    return {
      id: null,
      sourceElementId: elementId,
      parent: visualParentId,
      source: this.#sourceDescriptor(element, context),
      frame: this.#frame(rect, rootRect),
      localFrame: this.#frame(rect, parentRect),
      visibleFrame: this.#frame(visibleRect, rootRect),
      visibility: {
        currentlyVisible: visibleArea > 0,
        visibleArea: this.#round(visibleArea),
        scrollReachable: Boolean(scrollAncestor),
        effectiveOpacity: this.#effectiveOpacity(element),
        clipping: {
          any:
            visibleRect.width < rect.width - 0.5 ||
            visibleRect.height < rect.height - 0.5,
          top: visibleRect.top > rect.top + 0.5,
          right: visibleRect.right < rect.right - 0.5,
          bottom: visibleRect.bottom < rect.bottom - 0.5,
          left: visibleRect.left > rect.left + 0.5,
          visibleWidth: this.#ratio(
            visibleRect.width,
            Math.max(1e-9, rect.width),
          ),
          visibleHeight: this.#ratio(
            visibleRect.height,
            Math.max(1e-9, rect.height),
          ),
        },
      },
      transform:
        /** @type {SceneRecord | undefined} */
        (elementVisual?.[String("transform")]) ??
        this.#transformDescriptor(element, style, rect, parentRect, rootRect),
      layering:
        /** @type {SceneRecord | undefined} */
        (elementVisual?.[String("layering")]) ??
        this.#layeringDescriptor(element, style),
      interaction: {
        hovered: element.matches(":hover"),
        focused: element === document.activeElement,
        focusWithin: element.matches(":focus-within"),
        pointerEvents: style.pointerEvents,
        cursor: style.cursor,
      },
    };
  };
  /**
   * Describe a painted element background and its visible geometry.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneObject|null} Captured surfacePrimitive evidence for the calling operation.
   */
  static #surfacePrimitive = (element, style, meta, context) => {
    const backgroundColor = this.#parseColor(style.backgroundColor);
    const hasImage = style.backgroundImage !== "none";
    if (!(backgroundColor && backgroundColor[3] > 0) && !hasImage) return null;
    return {
      ...meta,
      id: this.#nextObjectId(context, "surface"),
      type: "surface",
      appearance: {
        background: {
          color: this.#colorDescriptor(backgroundColor),
          image: hasImage ? style.backgroundImage : null,
          size: style.backgroundSize,
          position: style.backgroundPosition,
          repeat: style.backgroundRepeat,
          blendMode: style.backgroundBlendMode,
        },
        mixBlendMode: style.mixBlendMode,
        filter: style.filter === "none" ? null : style.filter,
        backdropFilter: this.#backdropFilter(style),
        shape: this.#shapeDescriptor(style, element.getBoundingClientRect()),
      },
      paintConfidence: hasImage
        ? "computed-style-not-final-pixels"
        : "solid-background-exact",
    };
  };
  /**
   * Rasterize an image, video or canvas into a visible media primitive.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {Promise<SceneObject|null>} Captured mediaPrimitive evidence for the calling operation.
   */
  static #mediaPrimitive = async (element, style, meta, context) => {
    const type =
      element instanceof HTMLImageElement
        ? "image"
        : element instanceof HTMLCanvasElement
          ? "canvas"
          : element instanceof HTMLVideoElement
            ? "video"
            : element instanceof SVGSVGElement
              ? "svg-raster"
              : null;
    if (!type) return null;
    const raster = await this.#rasterizeMedia(element, style, meta, context);
    const canvasElement = element instanceof HTMLCanvasElement ? element : null;
    const canvasRect = canvasElement?.getBoundingClientRect() ?? null;
    if (raster?.canvas) context.rasterCache.set(element, raster);
    return {
      ...meta,
      id: this.#nextObjectId(
        context,
        type === "svg-raster" ? "svg-render" : type,
      ),
      type: type === "svg-raster" ? "svg-render" : type,
      appearance: {
        objectFit: style.objectFit,
        objectPosition: style.objectPosition,
        opacity: Number(style.opacity),
        effectiveOpacity: meta.visibility.effectiveOpacity,
        mixBlendMode: style.mixBlendMode,
        filter: style.filter === "none" ? null : style.filter,
        backdropFilter: this.#backdropFilter(style),
      },
      ...(canvasElement &&
        canvasRect && {
          canvas: {
            intrinsic: {
              width: canvasElement.width,
              height: canvasElement.height,
              pixels: canvasElement.width * canvasElement.height,
              aspectRatio: canvasElement.height
                ? this.#round(canvasElement.width / canvasElement.height)
                : null,
            },
            css: {
              width: this.#round(canvasRect.width),
              height: this.#round(canvasRect.height),
            },
            backingPixelsPerCssPixel: {
              x: canvasRect.width
                ? this.#round(canvasElement.width / canvasRect.width)
                : null,
              y: canvasRect.height
                ? this.#round(canvasElement.height / canvasRect.height)
                : null,
            },
            attributes: {
              width: element.getAttribute("width"),
              height: element.getAttribute("height"),
            },
            visibleRaster: raster
              ? {
                  width: raster.canvas.width,
                  height: raster.canvas.height,
                  readable: Boolean(raster.binary),
                  averageColor: raster.stats.averageColor,
                  luminance: raster.stats.luminance,
                  alpha: raster.stats.alpha,
                  colorRegions: raster.stats.regions,
                }
              : null,
          },
        }),
      raster: raster
        ? {
            mime: raster.mime,
            binary: context.settings.includeBinary ? raster.binary : null,
            dimensionsRelativeToReference: {
              width: this.#ratio(raster.canvas.width, context.rootRect.width),
              height: this.#ratio(
                raster.canvas.height,
                context.rootRect.height,
              ),
            },
            averageColor: raster.stats.averageColor,
            averageContrast: raster.stats.averageContrast,
            colorGrid: raster.stats.grid,
            colorGridDefinition: raster.stats.gridDefinition,
            colorGridContrast: raster.stats.gridContrast,
            colorRegions: raster.stats.regions,
            colorRegionDefinition: raster.stats.regionDefinition,
            luminance: raster.stats.luminance,
            alpha: raster.stats.alpha,
            composition: raster.composition,
            accuracy: raster.accuracy,
          }
        : null,
    };
  };
  /**
   * Retain SVG vector markup and pair it with the sampled raster evidence.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {?SceneObject} rasterObject Rasterobject used by this operation.
   * @returns {SceneObject} Captured svgPrimitive evidence for the calling operation.
   */
  static #svgPrimitive = (element, style, meta, rasterObject) => {
    /** @type {?SceneFrame} */
    let bbox = null;
    try {
      const raw = /** @type {SVGSVGElement} */ (element).getBBox();
      const view = /** @type {SVGSVGElement} */ (element).viewBox.baseVal;
      if (view?.width && view?.height)
        bbox = {
          x: this.#ratio(raw.x - view.x, view.width),
          y: this.#ratio(raw.y - view.y, view.height),
          width: this.#ratio(raw.width, view.width),
          height: this.#ratio(raw.height, view.height),
        };
    } catch {
      // Detached SVG geometry is unavailable; preserve a null view-box sample.
    }
    return {
      ...meta,
      id: `${meta.sourceElementId}-svg-vector`,
      type: "svg",
      markup: element.outerHTML,
      styledMarkup: this.#serializeStyledSvg(element),
      viewBox: element.getAttribute("viewBox"),
      visibleBoundingBox: meta.visibleFrame,
      vectorBoundingBox: bbox,
      vectorElements: this.#svgVectorElements(element),
      strokeSummary: this.#svgStrokeSummary(element),
      appearance: {
        opacity: Number(style.opacity),
        mixBlendMode: style.mixBlendMode,
        filter: style.filter === "none" ? null : style.filter,
      },
      renderedCompanion: rasterObject?.id ?? null,
    };
  };
  /**
   * Describe visible text, typography and source geometry.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneObject|null} Captured textPrimitive evidence for the calling operation.
   */
  static #textPrimitive = (element, style, meta, context) => {
    const nodes = [...element.childNodes].filter(
      node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
    );
    if (!nodes.length) return null;
    /** @type {SceneTextLineBox[]} */
    const lines = [];
    for (const node of nodes) {
      const text = node.textContent ?? "";
      for (const match of text.matchAll(/\S+(?:\s+|$)/g)) {
        const range = document.createRange();
        range.setStart(node, match.index);
        range.setEnd(
          node,
          Math.min(text.length, match.index + match[0].length),
        );
        for (const rect of range.getClientRects()) {
          if (rect.width <= 0 || rect.height <= 0) continue;
          let line = lines.find(
            entry => Math.abs(entry.top - rect.top) <= 1.5,
          );
          if (!line) {
            line = {
              top: rect.top,
              bottom: rect.bottom,
              left: rect.left,
              right: rect.right,
              text: "",
            };
            lines.push(line);
          }
          line.text += match[0] ?? "";
          line.left = Math.min(line.left, rect.left);
          line.right = Math.max(line.right, rect.right);
          line.top = Math.min(line.top, rect.top);
          line.bottom = Math.max(line.bottom, rect.bottom);
        }
      }
    }
    if (!lines.length) return null;
    lines.sort((a, b) => a.top - b.top || a.left - b.left);
    const heights = lines
      .map(line => line.bottom - line.top)
      .filter(value => value > 0);
    const medianHeight = heights.length
      ? (heights.sort((a, b) => a - b)[Math.floor(heights.length / 2)] ?? 0)
      : 0;
    /** @type {{text: string, frame: SceneFrame}[][]} */
    const paragraphs = [];
    /** @type {{text: string, frame: SceneFrame}[]} */
    let paragraph = [];
    /** @type {?SceneTextLineBox} */
    let previous = null;
    for (const line of lines) {
      const gap = previous ? line.top - previous.bottom : 0;
      if (paragraph.length && medianHeight && gap > medianHeight * 0.75) {
        paragraphs.push(paragraph);
        paragraph = [];
      }
      paragraph.push({
        text: line.text.trimEnd(),
        frame: this.#frame(
          {
            left: line.left,
            top: line.top,
            right: line.right,
            bottom: line.bottom,
            width: line.right - line.left,
            height: line.bottom - line.top,
          },
          context.rootRect,
        ),
      });
      previous = line;
    }
    if (paragraph.length) paragraphs.push(paragraph);
    const color = this.#parseColor(style.color);
    const content = paragraphs
      .map(group => group.map(line => line.text).join("\n"))
      .join("\n\n");
    const hasHorizontalOverflow =
      element.scrollWidth > element.clientWidth + 0.5;
    const hasVerticalOverflow =
      element.scrollHeight > element.clientHeight + 0.5;
    return {
      ...meta,
      id: this.#nextObjectId(context, "text"),
      type: "text",
      content,
      paragraphs: paragraphs.map(group => ({
        text: group.map(line => line.text).join("\n"),
        lines: group,
      })),
      appearance: {
        typography: this.#typography(
          style,
          element.getBoundingClientRect(),
          context.rootRect,
        ),
        color: this.#colorDescriptor(color),
        mixBlendMode: style.mixBlendMode,
        filter: style.filter === "none" ? null : style.filter,
      },
      overflow: {
        horizontal: hasHorizontalOverflow,
        vertical: hasVerticalOverflow,
        ellipsis: style.textOverflow === "ellipsis" && hasHorizontalOverflow,
        whiteSpace: style.whiteSpace,
        scroll: this.#scrollState(element),
      },
      contrast: {
        status: "pending-background-resolution",
      },
    };
  };
  /**
   * Describe visible borders, outlines and separators as scene primitives.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneObject[]} Captured edgePrimitives evidence for the calling operation.
   */
  static #edgePrimitives = (element, style, meta, context) => {
    const rect = element.getBoundingClientRect();
    const sides = {
      top: this.#borderSide(style, "Top"),
      right: this.#borderSide(style, "Right"),
      bottom: this.#borderSide(style, "Bottom"),
      left: this.#borderSide(style, "Left"),
    };
    const active = Object.entries(sides).filter(
      ([, side]) =>
        side.width > 0 && side.style !== "none" && (side.color?.[3] ?? 0) > 0,
    );
    /** @type {SceneObject[]} */
    const output = [];
    if (active.length >= 3)
      output.push({
        ...meta,
        id: this.#nextObjectId(context, "contour"),
        type: "contour",
        sourceKind: "border",
        sides: Object.fromEntries(
          active.map(([name, side]) => [
            name,
            {
              thickness: this.#ratio(
                side.width,
                name === "top" || name === "bottom"
                  ? Math.max(1, rect.height)
                  : Math.max(1, rect.width),
              ),
              style: side.style,
              stroke: this.#cssStrokeDescriptor(
                side.style,
                side.width,
                rect,
                name,
              ),
              color: this.#colorDescriptor(side.color),
            },
          ]),
        ),
        shape: this.#shapeDescriptor(style, rect),
      });
    else
      for (const [side, data] of active)
        output.push(
          this.#lineFromBorder(side, data, rect, style, meta, context),
        );
    const outlineWidth = parseFloat(style.outlineWidth);
    const outlineColor = this.#parseColor(style.outlineColor);
    if (
      style.outlineStyle !== "none" &&
      outlineWidth > 0 &&
      (outlineColor?.[3] ?? 0) > 0
    )
      output.push({
        ...meta,
        id: this.#nextObjectId(context, "contour"),
        type: "contour",
        sourceKind: "outline",
        style: style.outlineStyle,
        color: this.#colorDescriptor(outlineColor),
        thickness: this.#ratio(
          outlineWidth,
          Math.max(1, Math.min(rect.width, rect.height)),
        ),
        offset: this.#ratio(
          parseFloat(style.outlineOffset),
          Math.max(1, Math.min(rect.width, rect.height)),
        ),
        shape: this.#shapeDescriptor(style, rect),
        stroke: this.#cssStrokeDescriptor(
          style.outlineStyle,
          outlineWidth,
          rect,
          "outline",
        ),
      });
    return output;
  };
  /**
   * Derive line from border for the current rendered scene.
   * @param {string} side Side used by this operation.
   * @param {SceneBorderSide} data Data used by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneObject} Captured lineFromBorder evidence for the calling operation.
   */
  static #lineFromBorder = (side, data, rect, style, meta, context) => {
    const horizontal = side === "top" || side === "bottom";
    return {
      ...meta,
      id: this.#nextObjectId(context, "line"),
      type: "line",
      role: horizontal ? "horizontal-separator" : "vertical-separator",
      sourceKind: `border-${side}`,
      orientation: horizontal ? "horizontal" : "vertical",
      frame: horizontal
        ? {
            x: meta.frame.x,
            y:
              side === "top"
                ? meta.frame.y
                : this.#round(meta.frame.y + meta.frame.height),
            width: meta.frame.width,
            height: 0,
          }
        : {
            x:
              side === "left"
                ? meta.frame.x
                : this.#round(meta.frame.x + meta.frame.width),
            y: meta.frame.y,
            width: 0,
            height: meta.frame.height,
          },
      thickness: this.#ratio(
        data.width,
        horizontal ? Math.max(1, rect.height) : Math.max(1, rect.width),
      ),
      style: data.style,
      stroke: this.#cssStrokeDescriptor(data.style, data.width, rect, side),
      edgeGeometry: this.#borderEdgeGeometry(side, style, rect),
      color: this.#colorDescriptor(data.color),
    };
  };
  /**
   * Describe the current semantic role, state and affordances of a control.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @returns {SceneObject|null} Captured controlPrimitive evidence for the calling operation.
   */
  static #controlPrimitive = (element, style, meta) => {
    const semanticType = this.#controlSemanticType(element);
    if (!semanticType) return null;
    const role = element.getAttribute("role")?.trim().toLowerCase() || null;
    const output = /** @type {SceneObject} */ ({
      ...meta,
      id: `${meta.sourceElementId}-control`,
      type: "control",
      semanticType,
      implementation: role ? "aria/custom" : "native-html",
      role:
        role ??
        (semanticType === "spinbox"
          ? "spinbutton"
          : ["toggle-button", "disclosure-button"].includes(semanticType)
            ? "button"
            : semanticType === "meter"
              ? "meter"
              : semanticType === "file-picker" ||
                  semanticType === "color-picker" ||
                  semanticType.endsWith("-picker")
                ? null
                : semanticType),
      name: this.#accessibleName(element),
      description:
        this.#cleanText(element.getAttribute("aria-description")) ||
        this.#idRefs(element, "aria-describedby")
          .map(id =>
            this.#cleanText(document.getElementById(id)?.textContent),
          )
          .filter(Boolean)
          .join(" ") ||
        null,
      state: this.#commonControlState(element),
      appearance: {
        accentColor:
          style.accentColor === "auto"
            ? null
            : this.#colorDescriptor(this.#parseColor(style.accentColor)),
        nativeAppearance: style.appearance,
        cursor: style.cursor,
      },
      affordances: this.#controlAffordances(element, semanticType),
    });
    const labelledBy = this.#idRefs(element, "aria-labelledby");
    const describedBy = this.#idRefs(element, "aria-describedby");
    const controls = this.#idRefs(element, "aria-controls");
    const owns = this.#idRefs(element, "aria-owns");
    if (
      labelledBy.length ||
      describedBy.length ||
      controls.length ||
      owns.length
    )
      output[String("relations")] = {
        ...(labelledBy.length
          ? {
              labelledBy,
            }
          : {}),
        ...(describedBy.length
          ? {
              describedBy,
            }
          : {}),
        ...(controls.length
          ? {
              controls,
            }
          : {}),
        ...(owns.length
          ? {
              owns,
            }
          : {}),
      };
    if (["button", "toggle-button", "disclosure-button"].includes(semanticType))
      output[String("action")] = this.#buttonAction(element, semanticType);
    if (semanticType === "link")
      output[String("action")] = this.#linkAction(element);
    if (
      ["slider", "spinbox", "scrollbar", "progressbar", "meter"].includes(
        semanticType,
      )
    ) {
      output[String("value")] = this.#numericControlValue(
        element,
        semanticType,
      );
      if (["slider", "scrollbar"].includes(semanticType)) {
        const value = /** @type {SceneRecord} */ (output[String("value")]);
        value[String("orientation")] =
          element.getAttribute("aria-orientation") ||
          (element.getBoundingClientRect().height >
          element.getBoundingClientRect().width
            ? "vertical"
            : "horizontal");
      }
    }
    if (["checkbox", "switch"].includes(semanticType))
      /** @type {SceneRecord} */
      (output[String("state")])[String("checked")] =
        this.#checkedState(element);
    if (semanticType === "radio") {
      /** @type {SceneRecord} */
      (output[String("state")])[String("checked")] =
        this.#checkedState(element);
      output[String("group")] = this.#radioGroupState(element);
    }
    if (["textbox", "searchbox"].includes(semanticType))
      Object.assign(output, this.#textControlState(element));
    if (["combobox", "listbox"].includes(semanticType))
      Object.assign(output, this.#selectionControlState(element, semanticType));
    if (semanticType === "option")
      Object.assign(output, this.#optionControlState(element));
    if (semanticType === "tab") {
      const tablist = element.closest('[role="tablist"]');
      const tabs = tablist ? [...tablist.querySelectorAll('[role="tab"]')] : [];
      output[String("tab")] = {
        selected: this.#ariaBoolean(element, "aria-selected") === true,
        controls: this.#idRefs(element, "aria-controls"),
        position: tabs.length ? Math.max(0, tabs.indexOf(element)) : null,
        count: tabs.length || null,
        orientation: tablist?.getAttribute("aria-orientation") || "horizontal",
      };
    }
    if (
      ["menuitem", "menuitemcheckbox", "menuitemradio", "treeitem"].includes(
        semanticType,
      )
    )
      output[String("item")] = this.#structuredItemState(element, semanticType);
    if (semanticType === "file-picker")
      output[String("file")] = this.#fileControlState(element);
    if (semanticType === "color-picker")
      output[String("color")] =
        element instanceof HTMLInputElement && element.type === "color"
          ? {
              value: element.value,
              color: this.#colorDescriptor(this.#parseColor(element.value)),
            }
          : null;
    if (
      [
        "date-picker",
        "time-picker",
        "datetime-picker",
        "month-picker",
        "week-picker",
      ].includes(semanticType)
    )
      output[String("value")] =
        element instanceof HTMLInputElement
          ? {
              value: element.value || null,
              min: element.min || null,
              max: element.max || null,
              step: element.step || null,
            }
          : null;
    return output;
  };
  /**
   * Derive control semantic type for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string|null} Captured controlSemanticType evidence for the calling operation.
   */
  static #controlSemanticType = element => {
    const role = element.getAttribute("role")?.trim().toLowerCase() || null;
    /** @type {Record<string, string>} */
    const roleMap = {
      button: "button",
      link: "link",
      slider: "slider",
      spinbutton: "spinbox",
      checkbox: "checkbox",
      switch: "switch",
      radio: "radio",
      textbox: "textbox",
      searchbox: "searchbox",
      combobox: "combobox",
      listbox: "listbox",
      option: "option",
      tab: "tab",
      menuitem: "menuitem",
      menuitemcheckbox: "menuitemcheckbox",
      menuitemradio: "menuitemradio",
      treeitem: "treeitem",
      scrollbar: "scrollbar",
      progressbar: "progressbar",
    };
    if (role && roleMap[role]) return roleMap[role];
    if (element instanceof HTMLAnchorElement && element.hasAttribute("href"))
      return "link";
    if (element instanceof HTMLButtonElement)
      return element.hasAttribute("aria-pressed")
        ? "toggle-button"
        : element.hasAttribute("aria-expanded")
          ? "disclosure-button"
          : "button";
    if (element.tagName === "SUMMARY") return "disclosure-button";
    if (element instanceof HTMLTextAreaElement) return "textbox";
    if (element instanceof HTMLSelectElement)
      return element.multiple || element.size > 1 ? "listbox" : "combobox";
    if (element instanceof HTMLOptionElement) return "option";
    if (element instanceof HTMLProgressElement) return "progressbar";
    if (element instanceof HTMLMeterElement) return "meter";
    if (element instanceof HTMLInputElement)
      return (
        /** @type {Record<string, string>} */
        ({
          button: "button",
          submit: "button",
          reset: "button",
          image: "button",
          range: "slider",
          number: "spinbox",
          checkbox: "checkbox",
          radio: "radio",
          search: "searchbox",
          text: "textbox",
          email: "textbox",
          password: "textbox",
          tel: "textbox",
          url: "textbox",
          file: "file-picker",
          color: "color-picker",
          date: "date-picker",
          time: "time-picker",
          "datetime-local": "datetime-picker",
          month: "month-picker",
          week: "week-picker",
        })[element.type] ?? null
      );
    if (element instanceof HTMLElement && element.isContentEditable)
      return role === "searchbox" ? "searchbox" : "textbox";
    return null;
  };
  /**
   * Derive common control state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured commonControlState evidence for the calling operation.
   */
  static #commonControlState = element => {
    const validityState =
      "validity" in element && element.validity
        ? /** @type {ValidityState} */ (element.validity)
        : null;
    const validity = validityState
      ? {
          valid: Boolean(validityState.valid),
          valueMissing: Boolean(validityState.valueMissing),
          typeMismatch: Boolean(validityState.typeMismatch),
          patternMismatch: Boolean(validityState.patternMismatch),
          tooLong: Boolean(validityState.tooLong),
          tooShort: Boolean(validityState.tooShort),
          rangeUnderflow: Boolean(validityState.rangeUnderflow),
          rangeOverflow: Boolean(validityState.rangeOverflow),
          stepMismatch: Boolean(validityState.stepMismatch),
          badInput: Boolean(validityState.badInput),
          customError: Boolean(validityState.customError),
        }
      : null;
    /** @type {SceneRecord} */
    const state = {
      disabled:
        "disabled" in element && Boolean(element.disabled) ||
        this.#ariaBoolean(element, "aria-disabled") === true,
      readOnly:
        "readOnly" in element && Boolean(element.readOnly) ||
        this.#ariaBoolean(element, "aria-readonly") === true,
      required:
        "required" in element && Boolean(element.required) ||
        this.#ariaBoolean(element, "aria-required") === true,
      focused: element === document.activeElement,
      hovered: element.matches(":hover"),
      focusVisible: element.matches(":focus-visible"),
      tabIndex: element instanceof HTMLElement ? element.tabIndex : null,
    };
    const expanded = this.#ariaBoolean(element, "aria-expanded");
    const pressed = this.#ariaTriState(element, "aria-pressed");
    const selected = this.#ariaBoolean(element, "aria-selected");
    const busy = this.#ariaBoolean(element, "aria-busy");
    const invalid = element.getAttribute("aria-invalid");
    if (expanded !== null) state[String("expanded")] = expanded;
    if (pressed !== null) state[String("pressed")] = pressed;
    if (selected !== null) state[String("selected")] = selected;
    if (busy !== null) state[String("busy")] = busy;
    if (invalid !== null || validity)
      state[String("validation")] = {
        invalid:
          invalid && invalid !== "false"
            ? invalid
            : validity
              ? !validity.valid
              : false,
        validity,
        message:
          "validationMessage" in element && element.validationMessage
            ? /** @type {?string} */ (element.validationMessage)
            : null,
      };
    const current = element.getAttribute("aria-current");
    if (current && current !== "false")
      state[String("current")] = current === "true" ? true : current;
    const orientation = element.getAttribute("aria-orientation");
    if (orientation) state[String("orientation")] = orientation;
    const hasPopup = element.getAttribute("aria-haspopup");
    if (hasPopup && hasPopup !== "false")
      state[String("hasPopup")] = hasPopup === "true" ? true : hasPopup;
    const activeDescendant = element.getAttribute("aria-activedescendant");
    if (activeDescendant) state[String("activeDescendant")] = activeDescendant;
    return state;
  };
  /**
   * Read native and ARIA naming evidence for a rendered element.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {?Element} element Live DOM element observed or managed by this operation.
   * @returns {string|null} Captured accessibleName evidence for the calling operation.
   */
  static #accessibleName = element => {
    if (!element) return null;
    const ariaLabel = this.#cleanText(element.getAttribute("aria-label"));
    if (ariaLabel) return ariaLabel;
    const labelledBy = this.#idRefs(element, "aria-labelledby")
      .map(id => this.#cleanText(document.getElementById(id)?.textContent))
      .filter(Boolean);
    if (labelledBy.length) return labelledBy.join(" ");
    const elementLabels =
      "labels" in element
        ? /** @type {NodeListOf<HTMLLabelElement> | null | undefined} */ (
            element.labels
          )
        : null;
    if (elementLabels?.length) {
      const labels = [...elementLabels]
        .map(label => this.#cleanText(label.textContent))
        .filter(Boolean);
      if (labels.length) return labels.join(" ");
    }
    if (element instanceof HTMLInputElement && element.type === "image") {
      const alt = this.#cleanText(element.alt);
      if (alt) return alt;
    }
    if (element instanceof HTMLImageElement) {
      const alt = this.#cleanText(element.alt);
      if (alt) return alt;
    }
    if (
      element instanceof HTMLInputElement &&
      ["button", "submit", "reset"].includes(element.type)
    ) {
      const value = this.#cleanText(element.value);
      if (value) return value;
    }
    const text = this.#cleanText(element.textContent);
    if (text) return text;
    return this.#cleanText(element.getAttribute("title"));
  };
  /**
   * Derive button action for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} semanticType Semantictype used by this operation.
   * @returns {SceneRecord} Captured buttonAction evidence for the calling operation.
   */
  static #buttonAction = (element, semanticType) => {
    /** @type {SceneRecord} */
    const action = {
      kind:
        semanticType === "toggle-button"
          ? "toggle"
          : semanticType === "disclosure-button"
            ? "disclosure"
            : "activate",
    };
    if (
      element instanceof HTMLButtonElement ||
      element instanceof HTMLInputElement
    ) {
      const type =
        element instanceof HTMLButtonElement ? element.type : element.type;
      action[String("nativeType")] = type;
      const form = element.form;
      if (form && ["submit", "image"].includes(type))
        action[String("form")] = {
          method: (
            element.getAttribute("formmethod") ||
            form.method ||
            "get"
          ).toLowerCase(),
          action: element.formAction || form.action || location.href,
          target: element.formTarget || form.target || null,
        };
    }
    const expanded = this.#ariaBoolean(element, "aria-expanded");
    if (expanded !== null) action[String("expanded")] = expanded;
    const controls = this.#idRefs(element, "aria-controls");
    if (controls.length) action[String("controls")] = controls;
    if (
      element.tagName === "SUMMARY" &&
      element.parentElement instanceof HTMLDetailsElement
    )
      action[String("expanded")] = element.parentElement.open;
    return action;
  };
  /**
   * Classify a link destination without invoking it.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured linkAction evidence for the calling operation.
   */
  static #linkAction = element => {
    const href =
      element instanceof HTMLAnchorElement
        ? element.href
        : element.getAttribute("href");
    let destinationKind = "unknown";
    let external = null;
    if (href) {
      try {
        const url = new URL(href, document.baseURI);
        external = url.origin !== location.origin;
        destinationKind =
          url.protocol === "mailto:"
            ? "email"
            : url.protocol === "tel:"
              ? "telephone"
              : url.protocol.slice(0, -1) === "javascript"
                ? "script"
                : url.origin === location.origin &&
                    url.pathname === location.pathname &&
                    url.hash
                  ? "same-page-fragment"
                  : external
                    ? "external-page"
                    : "internal-page";
      } catch {
        // Malformed href remains an unknown destination in the description.
      }
    }
    return {
      kind: "navigate",
      href: href || null,
      destinationKind,
      external,
      target: element.getAttribute("target") || null,
      download:
        element instanceof HTMLAnchorElement && element.hasAttribute("download")
          ? element.download || true
          : false,
      rel: element.getAttribute("rel")?.split(/\s+/).filter(Boolean) ?? [],
    };
  };
  /**
   * Derive numeric control value for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} semanticType Semantictype used by this operation.
   * @returns {SceneRecord} Captured numericControlValue evidence for the calling operation.
   */
  static #numericControlValue = (element, semanticType) => {
    /**
     * Derive read number for the current rendered scene.
     * @param {string} attribute Attribute used by this operation.
     * @param {number | null} [fallback] Fallback used by this operation.
     * @returns {number|null} Parsed numeric value or fallback.
     */
    const readNumber = (attribute, fallback = null) => {
      const aria = element.getAttribute(`aria-value${attribute}`);
      if (aria !== null && aria.trim() && Number.isFinite(Number(aria)))
        return Number(aria);
      const key = attribute === "now" ? "value" : attribute;
      if (key in element) {
        const property =
          /** @type {Record<string, unknown>} */
          (
            /** @type {unknown} */
            (element)
          )[key];
        if (typeof property === "number" && Number.isFinite(property))
          return property;
        if (
          typeof property === "string" &&
          property.trim() &&
          Number.isFinite(Number(property))
        )
          return Number(property);
      }
      const raw = element.getAttribute(key);
      return raw !== null && raw.trim() && Number.isFinite(Number(raw))
        ? Number(raw)
        : fallback;
    };
    const defaultRange = ["slider", "scrollbar", "progressbar"].includes(
      semanticType,
    );
    let min = readNumber("min", defaultRange ? 0 : null);
    let max = readNumber("max", defaultRange ? 100 : null);
    const value = readNumber("now", 0) ?? 0;
    if (element instanceof HTMLProgressElement) {
      min = 0;
      max = element.max;
    } else if (element instanceof HTMLMeterElement) {
      min = element.min;
      max = element.max;
    }
    const span = min !== null && max !== null ? max - min : null;
    const stepRaw = element.getAttribute("step");
    const step =
      stepRaw === "any"
        ? "any"
        : stepRaw !== null && Number.isFinite(Number(stepRaw))
          ? Number(stepRaw)
          : semanticType === "slider"
            ? 1
            : null;
    /** @type {SceneRecord} */
    const result = {
      current: value,
      min,
      max,
      normalized:
        span !== null && min !== null
          ? this.#round((value - min) / span)
          : null,
      atMin: min !== null ? value <= min : null,
      atMax: max !== null ? value >= max : null,
      step,
      text: this.#cleanText(element.getAttribute("aria-valuetext")),
    };
    if (element instanceof HTMLInputElement && element.type === "range") {
      const list = /** @type {?HTMLDataListElement} */ (element.list);
      if (list)
        result[String("ticks")] = [...list.options].map(option => ({
          value: Number.isFinite(Number(option.value))
            ? Number(option.value)
            : option.value,
          label: this.#cleanText(option.label || option.textContent),
        }));
    }
    if (semanticType === "meter" && element instanceof HTMLMeterElement) {
      result[String("low")] = element.low;
      result[String("high")] = element.high;
      result[String("optimum")] = element.optimum;
      result[String("zone")] =
        element.value < element.low
          ? "low"
          : element.value > element.high
            ? "high"
            : "middle";
    }
    return result;
  };
  /**
   * Derive checked state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {boolean|string} Captured checkedState evidence for the calling operation.
   */
  static #checkedState = element => {
    if (
      element instanceof HTMLInputElement &&
      ["checkbox", "radio"].includes(element.type)
    )
      return element.indeterminate ? "mixed" : element.checked;
    return this.#ariaTriState(element, "aria-checked") ?? false;
  };
  /**
   * Derive radio group state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord|null} Captured radioGroupState evidence for the calling operation.
   */
  static #radioGroupState = element => {
    if (
      element instanceof HTMLInputElement &&
      element.type === "radio" &&
      element.name
    ) {
      const group = /** @type {HTMLInputElement[]} */ ([
        ...document.querySelectorAll(
          `input[type="radio"][name="${CSS.escape(element.name)}"]`,
        ),
      ]).filter(item => item.form === element.form);
      return {
        name: element.name,
        count: group.length,
        position: Math.max(0, group.indexOf(element)),
        checkedValue: group.find(item => item.checked)?.value ?? null,
      };
    }
    const group = element.closest('[role="radiogroup"]');
    if (!group) return null;
    const radios = [...group.querySelectorAll('[role="radio"]')];
    return {
      name: this.#accessibleName(group),
      count: radios.length,
      position: Math.max(0, radios.indexOf(element)),
      checkedName: this.#accessibleName(
        radios.find(
          item => this.#ariaTriState(item, "aria-checked") === true,
        ) ?? null,
      ),
    };
  };
  /**
   * Derive text control state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured textControlState evidence for the calling operation.
   */
  static #textControlState = element => {
    /** @type {SceneRecord} */
    const state = {
      multiline:
        element instanceof HTMLTextAreaElement ||
        element.getAttribute("aria-multiline") === "true",
      placeholder:
        "placeholder" in element
          ? this.#cleanText(
              /** @type {?string} */
              (element.placeholder),
            )
          : null,
      autocomplete:
        element.getAttribute("autocomplete") ||
        element.getAttribute("aria-autocomplete") ||
        null,
    };
    if (element instanceof HTMLInputElement) {
      state[String("inputType")] = element.type;
      if (element.type === "password") {
        state[String("masked")] = true;
        state[String("valueLength")] = element.value.length;
        state[String("visibleValue")] = element.value.length
          ? "•".repeat(Math.min(element.value.length, 64))
          : "";
      } else state[String("value")] = element.value;
      state[String("minLength")] =
        element.minLength >= 0 ? element.minLength : null;
      state[String("maxLength")] =
        element.maxLength >= 0 ? element.maxLength : null;
      if (typeof element.selectionStart === "number")
        state[String("selection")] = {
          start: this.#ratio(
            element.selectionStart,
            Math.max(1, element.value.length),
          ),
          end: this.#ratio(
            element.selectionEnd ?? element.selectionStart,
            Math.max(1, element.value.length),
          ),
          direction: element.selectionDirection,
        };
    } else if (element instanceof HTMLTextAreaElement) {
      state[String("value")] = element.value;
      state[String("minLength")] =
        element.minLength >= 0 ? element.minLength : null;
      state[String("maxLength")] =
        element.maxLength >= 0 ? element.maxLength : null;
      state[String("selection")] = {
        start: this.#ratio(
          element.selectionStart ?? 0,
          Math.max(1, element.value.length),
        ),
        end: this.#ratio(
          element.selectionEnd ?? 0,
          Math.max(1, element.value.length),
        ),
        direction: element.selectionDirection,
      };
    } else if (element instanceof HTMLElement && element.isContentEditable) {
      state[String("value")] = this.#cleanText(element.innerText);
      state[String("contentEditable")] = element.contentEditable;
    } else
      state[String("value")] = this.#cleanText(
        element.getAttribute("aria-valuetext") || element.textContent,
      );
    return {
      textInput: state,
    };
  };
  /**
   * Derive selection control state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} semanticType Semantictype used by this operation.
   * @returns {SceneRecord} Captured selectionControlState evidence for the calling operation.
   */
  static #selectionControlState = (element, semanticType) => {
    /** @type {SceneOptionItem[]} */
    let options = [];
    /** @type {boolean} */
    let multiple;
    /** @type {number[]} */
    let selected = [];
    /** @type {number | null} */
    let active;
    if (element instanceof HTMLSelectElement) {
      multiple = element.multiple;
      options = [...element.options].map((option, index) => ({
        index,
        label: this.#cleanText(option.label || option.textContent),
        value: option.value,
        selected: option.selected,
        disabled: option.disabled,
        hidden: option.hidden,
        group:
          option.parentElement instanceof HTMLOptGroupElement
            ? this.#cleanText(option.parentElement.label)
            : null,
      }));
      selected = options
        .filter(option => option.selected)
        .map(option => option.index);
      active = element.selectedIndex >= 0 ? element.selectedIndex : null;
    } else {
      multiple = this.#ariaBoolean(element, "aria-multiselectable") === true;
      const ids = [
        ...this.#idRefs(element, "aria-controls"),
        ...this.#idRefs(element, "aria-owns"),
      ];
      const roots = [
        element,
        ...ids.map(id => document.getElementById(id)).filter(Boolean),
      ];
      const seen = new Set();
      for (const root of roots)
        for (const option of root?.querySelectorAll?.('[role="option"]') ??
          []) {
          if (seen.has(option)) continue;
          seen.add(option);
          const entry = {
            index: options.length,
            label: this.#accessibleName(option),
            value:
              option.getAttribute("data-value") ??
              option.getAttribute("value") ??
              null,
            selected: this.#ariaBoolean(option, "aria-selected") === true,
            disabled: this.#ariaBoolean(option, "aria-disabled") === true,
            hidden: !this.#isRendered(option, 0.001),
          };
          options.push(entry);
          if (entry.selected) selected.push(entry.index);
        }
      const activeId = element.getAttribute("aria-activedescendant");
      active = activeId
        ? options.findIndex(entry => {
            const option = document.getElementById(activeId);
            return option
              ? entry.label === this.#accessibleName(option)
              : false;
          })
        : null;
      if (active === -1) active = null;
    }
    return {
      selection: {
        mode: semanticType,
        multiple,
        count: options.length,
        selected,
        active,
        value:
          element instanceof HTMLSelectElement
            ? element.value
            : (element.getAttribute("aria-valuetext") ?? null),
        expanded: this.#ariaBoolean(element, "aria-expanded"),
        options,
      },
    };
  };
  /**
   * Derive option control state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured optionControlState evidence for the calling operation.
   */
  static #optionControlState = element => {
    const selected =
      element instanceof HTMLOptionElement
        ? element.selected
        : this.#ariaBoolean(element, "aria-selected") === true;
    const disabled =
      element instanceof HTMLOptionElement
        ? element.disabled
        : this.#ariaBoolean(element, "aria-disabled") === true;
    return {
      option: {
        label:
          element instanceof HTMLOptionElement
            ? this.#cleanText(element.label || element.textContent)
            : this.#accessibleName(element),
        value:
          element instanceof HTMLOptionElement
            ? element.value
            : (element.getAttribute("data-value") ??
              element.getAttribute("value") ??
              null),
        selected,
        disabled,
        position: this.#integerAttribute(element, "aria-posinset"),
        setSize: this.#integerAttribute(element, "aria-setsize"),
      },
    };
  };
  /**
   * Derive structured item state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} semanticType Semantictype used by this operation.
   * @returns {SceneRecord} Captured structuredItemState evidence for the calling operation.
   */
  static #structuredItemState = (element, semanticType) =>
    Object.fromEntries(
      Object.entries({
        kind: semanticType,
        selected: this.#ariaBoolean(element, "aria-selected"),
        expanded: this.#ariaBoolean(element, "aria-expanded"),
        checked: ["menuitemcheckbox", "menuitemradio"].includes(semanticType)
          ? this.#ariaTriState(element, "aria-checked")
          : null,
        level: this.#integerAttribute(element, "aria-level"),
        position: this.#integerAttribute(element, "aria-posinset"),
        setSize: this.#integerAttribute(element, "aria-setsize"),
      }).filter(([, value]) => value !== null),
    );
  /**
   * Derive file control state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord|null} Captured fileControlState evidence for the calling operation.
   */
  static #fileControlState = element => {
    if (!(element instanceof HTMLInputElement) || element.type !== "file")
      return null;
    return {
      multiple: element.multiple,
      accept: element.accept
        ? element.accept
            .split(",")
            .map(value => value.trim())
            .filter(Boolean)
        : [],
      count: element.files?.length ?? 0,
      files: [...(element.files ?? [])].map(file => ({
        name: file.name,
        type: file.type || null,
      })),
    };
  };
  /**
   * Derive control affordances for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} semanticType Semantictype used by this operation.
   * @returns {SceneRecord} Captured controlAffordances evidence for the calling operation.
   */
  static #controlAffordances = (element, semanticType) => {
    const actions = [
      ...({
        button: ["activate"],
        "toggle-button": ["toggle"],
        "disclosure-button": ["expand", "collapse"],
        link: ["navigate"],
        slider: ["set-value", "increment", "decrement"],
        spinbox: ["enter-value", "increment", "decrement"],
        checkbox: ["toggle"],
        switch: ["toggle"],
        radio: ["select"],
        textbox: ["enter-text", "select-text"],
        searchbox: ["enter-search-text", "select-text"],
        combobox: ["open-options", "choose-option"],
        listbox: ["choose-option"],
        option: ["select"],
        tab: ["activate-tab"],
        menuitem: ["activate"],
        menuitemcheckbox: ["toggle"],
        menuitemradio: ["select"],
        treeitem: ["select", "expand", "collapse"],
        scrollbar: ["scroll", "set-position"],
        progressbar: [],
        meter: [],
        "file-picker": ["choose-file"],
        "color-picker": ["choose-color"],
        "date-picker": ["choose-date", "enter-value"],
        "time-picker": ["choose-time", "enter-value"],
        "datetime-picker": ["choose-date-time", "enter-value"],
        "month-picker": ["choose-month", "enter-value"],
        "week-picker": ["choose-week", "enter-value"],
      }[semanticType] ?? []),
    ];
    const disabled =
      "disabled" in element && Boolean(element.disabled) ||
      this.#ariaBoolean(element, "aria-disabled") === true;
    return {
      actions,
      interactive: actions.length > 0,
      available: !disabled,
    };
  };
  /**
   * Derive aria boolean for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} attribute Attribute used by this operation.
   * @returns {boolean|null} Captured ariaBoolean evidence for the calling operation.
   */
  static #ariaBoolean = (element, attribute) => {
    const value = element?.getAttribute?.(attribute);
    if (value === null || value === undefined) return null;
    if (value === "true") return true;
    if (value === "false") return false;
    return null;
  };
  /**
   * Derive aria tri state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} attribute Attribute used by this operation.
   * @returns {boolean|string|null} Captured ariaTriState evidence for the calling operation.
   */
  static #ariaTriState = (element, attribute) => {
    const value = element?.getAttribute?.(attribute);
    if (value === null || value === undefined) return null;
    if (value === "mixed") return "mixed";
    if (value === "true") return true;
    if (value === "false") return false;
    return null;
  };
  /**
   * Derive id refs for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} attribute Attribute used by this operation.
   * @returns {string[]} Captured idRefs evidence for the calling operation.
   */
  static #idRefs = (element, attribute) =>
    (element.getAttribute(attribute) || "").trim().split(/\s+/).filter(Boolean);
  /**
   * Derive integer attribute for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {string} attribute Attribute used by this operation.
   * @returns {number|null} Captured integerAttribute evidence for the calling operation.
   */
  static #integerAttribute = (element, attribute) => {
    const value = Number(element.getAttribute(attribute));
    return Number.isInteger(value) ? value : null;
  };
  /**
   * Derive clean text for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {string|null} Captured cleanText evidence for the calling operation.
   */
  static #cleanText = value =>
    String(value ?? "")
      .replace(/\s+/g, " ")
      .trim() || null;
  /**
   * Derive pseudo primitives for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneObject[]} Captured pseudoPrimitives evidence for the calling operation.
   */
  static #pseudoPrimitives = (element, meta, context) => {
    /** @type {SceneObject[]} */
    const result = [];
    for (const pseudo of ["::before", "::after"]) {
      const style = getComputedStyle(element, pseudo);
      const content = style.content;
      if (
        !content ||
        content === "none" ||
        content === "normal" ||
        style.display === "none" ||
        style.visibility === "hidden" ||
        Number(style.opacity) <= context.settings.opacityThreshold
      )
        continue;
      result.push({
        ...meta,
        id: this.#nextObjectId(context, "decoration"),
        type: "decoration",
        pseudo,
        source: {
          ...meta.source,
          visualSelector: `${String(meta.source[String("selector")] ?? "")}${pseudo}`,
          pseudo,
        },
        content,
        appearance: {
          color: this.#colorDescriptor(this.#parseColor(style.color)),
          backgroundColor: this.#colorDescriptor(
            this.#parseColor(style.backgroundColor),
          ),
          backgroundImage:
            style.backgroundImage === "none" ? null : style.backgroundImage,
          border: style.border,
          opacity: Number(style.opacity),
          filter: style.filter === "none" ? null : style.filter,
        },
        geometryConfidence: "pseudo-element-box-not-exposed-by-standard-dom",
      });
    }
    return result;
  };
  /**
   * Derive rasterize media for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {Promise<?SceneRaster>} Captured rasterizeMedia evidence for the calling operation.
   */
  static #rasterizeMedia = async (element, style, meta, context) => {
    const visible = this.#rectFromFrame(meta.visibleFrame, context.rootRect);
    if (visible.width <= 0 || visible.height <= 0) return null;
    const scale =
      context.settings.maxRasterDimension &&
      Math.max(visible.width, visible.height) >
        context.settings.maxRasterDimension
        ? context.settings.maxRasterDimension /
          Math.max(visible.width, visible.height)
        : 1;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(visible.width * scale));
    canvas.height = Math.max(1, Math.round(visible.height * scale));
    const draw = canvas.getContext("2d", {
      willReadFrequently: true,
    });
    if (!draw) return null;
    draw.scale(scale, scale);
    draw.filter = style.filter === "none" ? "none" : style.filter;
    draw.globalAlpha = this.#effectiveOpacity(element);
    let accuracy = "high";
    const rect = element.getBoundingClientRect();
    try {
      if (element instanceof HTMLImageElement) {
        if (
          !element.complete ||
          !element.naturalWidth ||
          !element.naturalHeight
        )
          return null;
        const fit = this.#objectFitRect(
          element.naturalWidth,
          element.naturalHeight,
          rect,
          style.objectFit,
          style.objectPosition,
        );
        draw.drawImage(
          element,
          fit.left - visible.left,
          fit.top - visible.top,
          fit.width,
          fit.height,
        );
      } else if (element instanceof HTMLCanvasElement)
        draw.drawImage(
          element,
          rect.left - visible.left,
          rect.top - visible.top,
          rect.width,
          rect.height,
        );
      else if (element instanceof HTMLVideoElement) {
        if (element.readyState < globalThis.HTMLMediaElement.HAVE_CURRENT_DATA)
          return null;
        const intrinsicWidth = element.videoWidth || rect.width;
        const intrinsicHeight = element.videoHeight || rect.height;
        const fit = this.#objectFitRect(
          intrinsicWidth,
          intrinsicHeight,
          rect,
          style.objectFit,
          style.objectPosition,
        );
        draw.drawImage(
          element,
          fit.left - visible.left,
          fit.top - visible.top,
          fit.width,
          fit.height,
        );
      } else if (element instanceof SVGSVGElement) {
        const image = await this.#svgImage(element);
        draw.drawImage(
          image,
          rect.left - visible.left,
          rect.top - visible.top,
          rect.width,
          rect.height,
        );
      }
    } catch (error) {
      context.warnings.push({
        sourceElementId: meta.sourceElementId,
        kind: "media-rasterization",
        message: String(error),
      });
      return null;
    }
    if (style.transform !== "none")
      accuracy = "reduced-css-transform-axis-aligned-raster";
    if (style.clipPath !== "none" || style.maskImage !== "none")
      accuracy = "reduced-mask-or-clip-path-not-applied-to-raster";
    const background = this.#effectiveFlatBackground(element, context.root);
    const stats = this.#colorStats(
      canvas,
      context.settings.gridColumns,
      context.settings.gridRows,
      background.color,
    );
    let binary = null;
    try {
      binary = canvas.toDataURL("image/png");
    } catch (error) {
      accuracy = "unavailable-cross-origin-canvas-security";
      context.warnings.push({
        sourceElementId: meta.sourceElementId,
        kind: "canvas-readback",
        message: String(error),
      });
    }
    const mixBlendMode = style.mixBlendMode;
    const composite = background.color
      ? this.#compositeMediaRaster(
          canvas,
          background.color,
          mixBlendMode,
          context.settings.gridColumns,
          context.settings.gridRows,
        )
      : null;
    return {
      canvas,
      visibleRect: visible,
      mime: "image/png",
      binary,
      stats,
      accuracy,
      composition: {
        cssFilterApplied: style.filter === "none" ? null : style.filter,
        effectiveOpacityApplied: this.#effectiveOpacity(element),
        mixBlendMode,
        backdropFilter: this.#backdropFilter(style),
        flatBackdrop: background.color
          ? this.#colorDescriptor(background.color)
          : null,
        compositedAgainstFlatBackdrop: composite
          ? {
              binary: context.settings.includeBinary ? composite.binary : null,
              averageColor: composite.stats.averageColor,
              averageContrast: composite.stats.averageContrast,
              colorGrid: composite.stats.grid,
              colorGridDefinition: composite.stats.gridDefinition,
              colorGridContrast: composite.stats.gridContrast,
              colorRegions: composite.stats.regions,
              colorRegionDefinition: composite.stats.regionDefinition,
              luminance: composite.stats.luminance,
              alpha: composite.stats.alpha,
            }
          : null,
        finalPixelConfidence: this.#backdropFilter(style)
          ? "reduced-backdrop-filter-final-pixels-unavailable"
          : background.exact
            ? "high-for-flat-ancestor-backdrop; underlying-sibling-content-may-change-result"
            : "approximate-flat-ancestor-backdrop; complex-background-or-underlying-content-may-change-result",
      },
    };
  };
  /**
   * Derive composite media raster for the current rendered scene.
   * @param {HTMLCanvasElement} canvas Canvas used by this operation.
   * @param {SceneRgba} background Background used by this operation.
   * @param {string} mixBlendMode Mixblendmode used by this operation.
   * @param {number} columns Columns used by this operation.
   * @param {number} rows Rows used by this operation.
   * @returns {?SceneCompositeRaster} Captured compositeMediaRaster evidence for the calling operation.
   */
  static #compositeMediaRaster = (
    canvas,
    background,
    mixBlendMode,
    columns,
    rows,
  ) => {
    const output = document.createElement("canvas");
    output.width = canvas.width;
    output.height = canvas.height;
    const context = output.getContext("2d", {
      willReadFrequently: true,
    });
    if (!context) return null;
    context.fillStyle = `rgba(${Math.round(background[0])}, ${Math.round(background[1])}, ${Math.round(background[2])}, ${this.#clamp(background[3], 0, 1)})`;
    context.fillRect(0, 0, output.width, output.height);
    context.globalCompositeOperation = [
      "multiply",
      "screen",
      "overlay",
      "darken",
      "lighten",
      "color-dodge",
      "color-burn",
      "hard-light",
      "soft-light",
      "difference",
      "exclusion",
      "hue",
      "saturation",
      "color",
      "luminosity",
    ].includes(mixBlendMode)
      ? /** @type {GlobalCompositeOperation} */ (mixBlendMode)
      : "source-over";
    context.drawImage(canvas, 0, 0);
    context.globalCompositeOperation = "source-over";
    /** @type {?string} */
    let binary = null;
    try {
      binary = output.toDataURL("image/png");
    } catch {
      // A tainted canvas cannot be exported; retain null PNG data.
    }
    return {
      canvas: output,
      binary,
      stats: this.#colorStats(output, columns, rows, background),
    };
  };
  /**
   * Derive color stats for the current rendered scene.
   * @param {HTMLCanvasElement} canvas Canvas used by this operation.
   * @param {number} columns Columns used by this operation.
   * @param {number} rows Rows used by this operation.
   * @param {?SceneRgba} [backdrop] Backdrop used by this operation.
   * @returns {SceneColorStats} Captured colorStats evidence for the calling operation.
   */
  static #colorStats = (canvas, columns, rows, backdrop = null) => {
    const context = canvas.getContext("2d", {
      willReadFrequently: true,
    });
    const gridColumns = this.#gridDimension(columns);
    const gridRows = this.#gridDimension(rows);
    const empty = {
      averageColor: null,
      averageContrast: null,
      grid: [],
      gridDefinition: {
        columns: gridColumns,
        rows: gridRows,
        neighbourhood: "8-connected",
        coordinates: "normalized-to-raster",
      },
      gridContrast: null,
      regions: [],
      regionDefinition: {
        connectivity: "4-connected",
        similarityContrastMaximum: 1.35,
        colorDistanceMaximum: 0.22,
      },
      luminance: null,
      alpha: null,
    };
    if (!context) return empty;
    let image;
    try {
      image = context.getImageData(0, 0, canvas.width, canvas.height);
    } catch {
      return empty;
    }
    /**
     * Derive sample for the current rendered scene.
     * @param {number} x0 X0 used by this operation.
     * @param {number} y0 Y0 used by this operation.
     * @param {number} x1 X1 used by this operation.
     * @param {number} y1 Y1 used by this operation.
     * @returns {SceneColorDescriptor} Sampled color value.
     */
    const sample = (x0, y0, x1, y1) => {
      let red = 0;
      let green = 0;
      let blue = 0;
      let alphaWeighted = 0;
      let alphaSum = 0;
      let count = 0;
      for (let y = y0; y < y1; y++)
        for (let x = x0; x < x1; x++) {
          const index = (y * canvas.width + x) * 4;
          const alpha = (image.data[index + 3] ?? 0) / 255;
          red += (image.data[index] ?? 0) * alpha;
          green += (image.data[index + 1] ?? 0) * alpha;
          blue += (image.data[index + 2] ?? 0) * alpha;
          alphaWeighted += alpha;
          alphaSum += alpha;
          count++;
        }
      const divisor = Math.max(alphaSum, 1e-9);
      return /** @type {SceneColorDescriptor} */ (
        this.#colorDescriptor([
          Math.round(red / divisor),
          Math.round(green / divisor),
          Math.round(blue / divisor),
          this.#round(alphaWeighted / Math.max(1, count)),
        ])
      );
    };
    const colors = Array.from(
      {
        length: gridRows,
      },
      (_, row) => {
        const y0 = Math.floor(row / gridRows * canvas.height);
        const y1 = Math.max(
          y0 + 1,
          Math.floor((row + 1) / gridRows * canvas.height),
        );
        return Array.from(
          {
            length: gridColumns,
          },
          (_unusedCell, column) => {
            const x0 = Math.floor(column / gridColumns * canvas.width);
            const x1 = Math.max(
              x0 + 1,
              Math.floor((column + 1) / gridColumns * canvas.width),
            );
            return sample(x0, y0, x1, y1);
          },
        );
      },
    );
    const averageColor = sample(0, 0, canvas.width, canvas.height);
    const contrast = this.#gridContrast(colors, averageColor, backdrop);
    const regions = this.#gridRegions(contrast.grid, backdrop);
    const flatColors = colors.flat();
    const luminances = flatColors
      .map(({ luminance }) => luminance)
      .filter(Number.isFinite);
    const alphas = flatColors
      .map(({ rgba }) => rgba[3] ?? 0)
      .filter(Number.isFinite);
    return {
      averageColor,
      averageContrast: {
        toBackdrop: backdrop
          ? this.#perceivedContrast(
              averageColor,
              this.#colorDescriptor(backdrop),
              backdrop,
            )
          : null,
        basis: backdrop ? "flat-backdrop-composited" : "isolated-rgb",
      },
      grid: contrast.grid,
      gridDefinition: {
        columns: gridColumns,
        rows: gridRows,
        neighbourhood: "8-connected",
        coordinates: "normalized-to-raster",
        cellWidth: this.#round(1 / gridColumns),
        cellHeight: this.#round(1 / gridRows),
      },
      gridContrast: contrast.summary,
      regions,
      regionDefinition: {
        connectivity: "4-connected",
        similarityContrastMaximum: 1.35,
        colorDistanceMaximum: 0.22,
        coordinates: "normalized-to-raster",
      },
      luminance: luminances.length
        ? {
            min: this.#round(Math.min(...luminances)),
            max: this.#round(Math.max(...luminances)),
            average: this.#round(
              luminances.reduce((sum, value) => sum + value, 0) /
                luminances.length,
            ),
          }
        : null,
      alpha: alphas.length
        ? {
            min: this.#round(Math.min(...alphas)),
            max: this.#round(Math.max(...alphas)),
            average: this.#round(
              alphas.reduce((sum, value) => sum + value, 0) / alphas.length,
            ),
          }
        : null,
    };
  };
  /**
   * Derive grid dimension for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {number} Captured gridDimension evidence for the calling operation.
   */
  static #gridDimension = value =>
    Math.max(1, Math.min(32, Math.round(Number(value) || 1)));
  /**
   * Derive grid contrast for the current rendered scene.
   * @param {SceneColorDescriptor[][]} colors Colors used by this operation.
   * @param {SceneColorDescriptor} averageColor Averagecolor used by this operation.
   * @param {?SceneRgba} backdrop Backdrop used by this operation.
   * @returns {SceneGridContrast} Captured gridContrast evidence for the calling operation.
   */
  static #gridContrast = (colors, averageColor, backdrop) => {
    const rows = colors.length;
    const columns = colors[0]?.length ?? 0;
    /** @type {[string, number, number][]} */
    const directions = [
      ["top", -1, 0],
      ["topRight", -1, 1],
      ["right", 0, 1],
      ["bottomRight", 1, 1],
      ["bottom", 1, 0],
      ["bottomLeft", 1, -1],
      ["left", 0, -1],
      ["topLeft", -1, -1],
    ];
    /** @type {[string, number, number][]} */
    const uniqueDirections = [
      ["right", 0, 1],
      ["bottomRight", 1, 1],
      ["bottom", 1, 0],
      ["bottomLeft", 1, -1],
    ];
    const grid = colors.map((rowColors, row) =>
      rowColors.map((color, column) => {
        const neighbours = Object.fromEntries(
          directions.flatMap(([name, rowOffset, columnOffset]) => {
            const neighbour = colors[row + rowOffset]?.[column + columnOffset];
            return neighbour
              ? /** @type {[string, number | null][]} */ ([
                  [name, this.#perceivedContrast(color, neighbour, backdrop)],
                ])
              : [];
          }),
        );
        const neighbourRatios = Object.values(neighbours).map(
          value => value ?? 0,
        );
        return {
          row,
          column,
          frame: {
            x: this.#round(column / columns),
            y: this.#round(row / rows),
            width: this.#round(1 / columns),
            height: this.#round(1 / rows),
          },
          color,
          contrast: {
            toAverage: this.#perceivedContrast(color, averageColor, backdrop),
            toBackdrop: backdrop
              ? this.#perceivedContrast(
                  color,
                  this.#colorDescriptor(backdrop),
                  backdrop,
                )
              : null,
            neighbours,
            minNeighbour: neighbourRatios.length
              ? this.#round(Math.min(...neighbourRatios))
              : null,
            maxNeighbour: neighbourRatios.length
              ? this.#round(Math.max(...neighbourRatios))
              : null,
            averageNeighbour: neighbourRatios.length
              ? this.#round(
                  neighbourRatios.reduce((sum, value) => sum + value, 0) /
                    neighbourRatios.length,
                )
              : null,
            wcag22GraphicalObjectIfMeaningful: {
              criterion: "1.4.11 Non-text Contrast",
              required: 3,
              applicability: "conditional-on-cell-boundary-carrying-meaning",
              strongestBoundaryPasses: neighbourRatios.length
                ? Math.max(...neighbourRatios) >= 3
                : null,
            },
          },
          perception: this.#salienceMetrics(
            neighbourRatios.length ? Math.max(...neighbourRatios) : 1,
            1 / Math.max(1, rows * columns),
            Math.min(1 / Math.max(1, columns), 1 / Math.max(1, rows)),
            1,
            1,
          ),
        };
      }),
    );
    const comparisons = colors.flatMap((rowColors, row) =>
      rowColors.flatMap((color, column) =>
        uniqueDirections.flatMap(([direction, rowOffset, columnOffset]) => {
          const targetRow = row + rowOffset;
          const targetColumn = column + columnOffset;
          const neighbour = colors[targetRow]?.[targetColumn];
          return neighbour
            ? [
                {
                  from: [row, column],
                  to: [targetRow, targetColumn],
                  direction,
                  ratio: this.#perceivedContrast(color, neighbour, backdrop),
                },
              ]
            : [];
        }),
      ),
    );
    const ratios = comparisons.map(({ ratio }) => ratio ?? 0);
    const sorted = [...comparisons].sort(
      (a, b) => (a.ratio ?? 0) - (b.ratio ?? 0),
    );
    return {
      grid,
      summary: ratios.length
        ? {
            basis: backdrop ? "flat-backdrop-composited" : "isolated-rgb",
            neighbourhood: "8-connected",
            comparisonCount: ratios.length,
            min: this.#round(Math.min(...ratios)),
            max: this.#round(Math.max(...ratios)),
            average: this.#round(
              ratios.reduce((sum, value) => sum + value, 0) / ratios.length,
            ),
            weakestBoundary: sorted[0] ?? null,
            strongestBoundary: sorted.at(-1) ?? null,
          }
        : null,
    };
  };
  /**
   * Derive perceived contrast for the current rendered scene.
   * @param {SceneColorLike} first First used by this operation.
   * @param {SceneColorLike} second Second used by this operation.
   * @param {?SceneRgba} backdrop Backdrop used by this operation.
   * @returns {number|null} Captured perceivedContrast evidence for the calling operation.
   */
  static #perceivedContrast = (first, second, backdrop) => {
    const firstColor = /** @type {SceneRgba | null | undefined} */ (
      Array.isArray(first) ? first : first?.rgba
    );
    const secondColor = /** @type {SceneRgba | null | undefined} */ (
      Array.isArray(second) ? second : second?.rgba
    );
    if (!firstColor || !secondColor) return null;
    /**
     * Derive resolve for the current rendered scene.
     * @param {SceneRgba} color Color used by this operation.
     * @returns {SceneRgba} Resolved RGBA color tuple.
     */
    const resolve = color =>
      backdrop && color[3] < 1 ? this.#alphaComposite(color, backdrop) : color;
    return this.#round(
      this.#contrastRatio(resolve(firstColor), resolve(secondColor)),
    );
  };
  /**
   * Derive resolve text contrast for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {void} Updates the capture context in place.
   */
  static #resolveTextContrast = context => {
    for (const object of context.objects) {
      if (object.type !== "text") continue;
      const source = this.#elementFromId(
        object.sourceElementId,
        context.root,
        context,
      );
      if (!source) continue;
      const style = getComputedStyle(source);
      const foreground = this.#parseColor(style.color);
      const paragraphs = /** @type {{lines: {frame: SceneFrame}[]}[]} */ (
        /** @type {unknown} */
        (object[String("paragraphs")])
      );
      const samplePoints = paragraphs.flatMap(({ lines }) =>
        lines.flatMap(({ frame }) => {
          const rect = this.#rectFromFrame(frame, context.rootRect);
          return [0.15, 0.5, 0.85].map(
            fraction =>
              /** @type {[number, number]} */ ([
                rect.left + rect.width * fraction,
                rect.top + rect.height * 0.5,
              ]),
          );
        }),
      );
      const samples = /** @type {SceneRecord[]} */ (
        samplePoints
          .map(([x, y]) => this.#backgroundSampleAt(source, x, y, context))
          .filter(Boolean)
      );
      if (!foreground || !samples.length) {
        object[String("contrast")] = {
          status: "unresolved",
          reason: "No readable background sample was available.",
        };
        continue;
      }
      const effectiveForeground = /** @type {SceneRgba} */ ([...foreground]);
      effectiveForeground[3] *= object.visibility.effectiveOpacity;
      const rawRatios = samples.map(sample => {
        const color = /** @type {SceneRgba} */ (sample[String("color")]);
        const resolvedForeground =
          effectiveForeground[3] < 1
            ? this.#alphaComposite(effectiveForeground, color)
            : effectiveForeground;
        return {
          ratio: this.#contrastRatio(resolvedForeground, color),
          source: sample[String("source")] ?? null,
          confidence: sample[String("confidence")] ?? null,
          background: this.#colorDescriptor(color),
        };
      });
      const rawValues = rawRatios.map(({ ratio }) => ratio);
      const minimum = Math.min(...rawValues);
      const fontSize = parseFloat(style.fontSize) || 0;
      const weight = Number(style.fontWeight);
      const bold = Number.isFinite(weight) && weight >= 700;
      const largeScale = fontSize >= 24 || (bold && fontSize >= 18.6666667);
      const aaRequired = largeScale ? 3 : 4.5;
      const aaaRequired = largeScale ? 4.5 : 7;
      object[String("contrast")] = {
        status: "resolved",
        min: this.#round(minimum),
        max: this.#round(Math.max(...rawValues)),
        average: this.#round(
          rawValues.reduce((sum, value) => sum + value, 0) / rawValues.length,
        ),
        samples: rawRatios.map(entry => ({
          ...entry,
          ratio: this.#round(entry.ratio),
        })),
        wcag22: {
          applicableAs: "text",
          textClass: largeScale ? "large-scale" : "normal",
          largeScale,
          classificationBasis: largeScale
            ? bold
              ? "at-least-14pt-bold-equivalent"
              : "at-least-18pt-equivalent"
            : "below-large-scale-threshold",
          AA: {
            criterion: "1.4.3 Contrast (Minimum)",
            required: aaRequired,
            passes: minimum >= aaRequired,
          },
          AAA: {
            criterion: "1.4.6 Contrast (Enhanced)",
            required: aaaRequired,
            passes: minimum >= aaaRequired,
          },
          thresholdComparison: "unrounded-ratio",
        },
      };
    }
  };
  /**
   * Derive background sample at for the current rendered scene.
   * @param {Element} textElement Textelement used by this operation.
   * @param {number} x X used by this operation.
   * @param {number} y Y used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {?SceneRecord} Captured backgroundSampleAt evidence for the calling operation.
   */
  static #backgroundSampleAt = (textElement, x, y, context) => {
    const stack = document.elementsFromPoint(x, y);
    const textIndex = stack.indexOf(textElement);
    const candidates = textIndex >= 0 ? stack.slice(textIndex + 1) : stack;
    for (const candidate of candidates) {
      if (!(candidate instanceof Element)) continue;
      const raster = context.rasterCache.get(candidate);
      if (
        raster &&
        x >= raster.visibleRect.left &&
        x <= raster.visibleRect.right &&
        y >= raster.visibleRect.top &&
        y <= raster.visibleRect.bottom
      ) {
        const color = this.#sampleRasterPoint(raster, x, y);
        if (color && color[3] > 0)
          return {
            color,
            source: "underlying-media-raster",
            confidence: "high",
          };
      }
      const color = this.#parseColor(
        getComputedStyle(candidate).backgroundColor,
      );
      if (color && color[3] > 0)
        return {
          color,
          source: "underlying-solid-background",
          confidence: "high",
        };
    }
    const fallback = this.#effectiveFlatBackground(textElement, context.root);
    return fallback.color
      ? {
          color: fallback.color,
          source: "ancestor-alpha-composited-background",
          confidence: fallback.exact ? "high" : "approximate",
        }
      : null;
  };
  /**
   * Derive sample raster point for the current rendered scene.
   * @param {SceneRaster} raster Raster used by this operation.
   * @param {number} x X used by this operation.
   * @param {number} y Y used by this operation.
   * @returns {?SceneRgba} Captured sampleRasterPoint evidence for the calling operation.
   */
  static #sampleRasterPoint = (raster, x, y) => {
    const rect = raster.visibleRect;
    const localX = this.#clamp(
      (x - rect.left) / Math.max(1e-9, rect.width),
      0,
      0.999999,
    );
    const localY = this.#clamp(
      (y - rect.top) / Math.max(1e-9, rect.height),
      0,
      0.999999,
    );
    const px = Math.floor(localX * raster.canvas.width);
    const py = Math.floor(localY * raster.canvas.height);
    try {
      const context = raster.canvas.getContext("2d", {
        willReadFrequently: true,
      });
      if (!context) return null;
      const data = context.getImageData(px, py, 1, 1).data;
      return [data[0] ?? 0, data[1] ?? 0, data[2] ?? 0, (data[3] ?? 0) / 255];
    } catch {
      return null;
    }
  };
  /**
   * Derive relationships for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {SceneRecord[]} Captured relationships evidence for the calling operation.
   */
  static #relationships = context => {
    const objects = context.objects.filter(
      object => object.frame && object.visibility?.currentlyVisible,
    );
    const relationships = [];
    for (let a = 0; a < objects.length; a++)
      for (let b = a + 1; b < objects.length; b++) {
        const first = objects[a];
        const second = objects[b];
        if (!first || !second) continue;
        const firstPolygon = this.#objectPolygon(first);
        const secondPolygon = this.#objectPolygon(second);
        const polygon = this.#polygonIntersection(firstPolygon, secondPolygon);
        const overlapArea = this.#polygonArea(polygon);
        if (polygon.length < 3 || overlapArea <= 1e-9) continue;
        const frame = this.#polygonBounds(polygon);
        const firstArea = Math.max(1e-9, this.#polygonArea(firstPolygon));
        const secondArea = Math.max(1e-9, this.#polygonArea(secondPolygon));
        const order = this.#visualOrder(first, second, polygon, context);
        relationships.push({
          type: "overlap",
          a: first.id,
          b: second.id,
          overlap: {
            geometry: "transformed-polygon-intersection",
            polygon,
            frame,
            area: this.#round(overlapArea),
            ofA: this.#round(overlapArea / firstArea),
            ofB: this.#round(overlapArea / secondArea),
          },
          stack: order,
          layer: order.topObjectId
            ? `${order.topObjectId}-above-${order.bottomObjectId}`
            : "undetermined",
          occlusion: {
            geometricOnly: true,
            estimatedEffectiveCoverageOfA:
              order.topObjectId === second.id
                ? this.#round(
                    overlapArea / firstArea *
                      (second.visibility?.effectiveOpacity ?? 1),
                  )
                : 0,
            estimatedEffectiveCoverageOfB:
              order.topObjectId === first.id
                ? this.#round(
                    overlapArea / secondArea *
                      (first.visibility?.effectiveOpacity ?? 1),
                  )
                : 0,
          },
        });
      }
    return relationships;
  };
  /**
   * Derive scroll state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneScrollState} Captured scrollState evidence for the calling operation.
   */
  static #scrollState = element => {
    const maxX = Math.max(0, element.scrollWidth - element.clientWidth);
    const maxY = Math.max(0, element.scrollHeight - element.clientHeight);
    return {
      x: {
        scrollable: maxX > 0.5,
        position: maxX ? this.#round(element.scrollLeft / maxX) : 0,
        viewportFraction: element.scrollWidth
          ? this.#round(element.clientWidth / element.scrollWidth)
          : 1,
        hiddenBefore: element.scrollWidth
          ? this.#round(element.scrollLeft / element.scrollWidth)
          : 0,
        hiddenAfter: element.scrollWidth
          ? this.#round(
              Math.max(
                0,
                element.scrollWidth - element.clientWidth - element.scrollLeft,
              ) / element.scrollWidth,
            )
          : 0,
      },
      y: {
        scrollable: maxY > 0.5,
        position: maxY ? this.#round(element.scrollTop / maxY) : 0,
        viewportFraction: element.scrollHeight
          ? this.#round(element.clientHeight / element.scrollHeight)
          : 1,
        hiddenBefore: element.scrollHeight
          ? this.#round(element.scrollTop / element.scrollHeight)
          : 0,
        hiddenAfter: element.scrollHeight
          ? this.#round(
              Math.max(
                0,
                element.scrollHeight - element.clientHeight - element.scrollTop,
              ) / element.scrollHeight,
            )
          : 0,
      },
    };
  };
  /**
   * Derive effective flat background for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {Element} stopAt Stopat used by this operation.
   * @returns {SceneBackdrop} Captured effectiveFlatBackground evidence for the calling operation.
   */
  static #effectiveFlatBackground = (element, stopAt) => {
    /** @type {SceneRgba} */
    let composed = [0, 0, 0, 0];
    let exact = true;
    /** @type {Element[]} */
    const chain = [];
    /** @type {Element | null} */
    let current = element;
    for (; current; current = current.parentElement) {
      chain.push(current);
      if (current === stopAt) break;
    }
    chain.reverse();
    for (const chainElement of chain) {
      const style = getComputedStyle(chainElement);
      if (style.backgroundImage !== "none") exact = false;
      const color = this.#parseColor(style.backgroundColor);
      if (color) composed = this.#alphaComposite(color, composed);
    }
    if (composed[3] < 1) {
      composed = this.#alphaComposite([255, 255, 255, 1], composed);
      exact = false;
    }
    return {
      color: composed,
      exact,
    };
  };
  /**
   * Derive svg paint value for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {string} property Property used by this operation.
   * @returns {string} Captured svgPaintValue evidence for the calling operation.
   */
  static #svgPaintValue = (style, property) => {
    const value = style.getPropertyValue(property).trim();
    return /^currentcolor$/i.test(value) ? style.color : value;
  };
  /**
   * Serialize SVG markup with the computed paint needed for rasterization.
   * @param {Element} svg Svg used by this operation.
   * @returns {string} Captured serializeStyledSvg evidence for the calling operation.
   */
  static #serializeStyledSvg = svg => {
    const clone = /** @type {Element} */ (svg.cloneNode(true));
    const originalNodes = [svg, ...svg.querySelectorAll("*")];
    const cloneNodes = [clone, ...clone.querySelectorAll("*")];
    const properties = [
      "fill",
      "fill-opacity",
      "fill-rule",
      "stroke",
      "stroke-opacity",
      "stroke-width",
      "stroke-linecap",
      "stroke-linejoin",
      "stroke-miterlimit",
      "stroke-dasharray",
      "stroke-dashoffset",
      "vector-effect",
      "marker-start",
      "marker-mid",
      "marker-end",
      "stop-color",
      "stop-opacity",
      "flood-color",
      "flood-opacity",
      "lighting-color",
      "clip-rule",
      "opacity",
      "color",
      "font-family",
      "font-size",
      "font-style",
      "font-weight",
      "letter-spacing",
      "text-anchor",
      "paint-order",
      "shape-rendering",
      "color-interpolation",
      "color-interpolation-filters",
      "filter",
      "clip-path",
      "mask",
      "mix-blend-mode",
    ];
    originalNodes.forEach((node, index) => {
      const target = cloneNodes[index];
      if (!(node instanceof Element) || !(target instanceof Element)) return;
      const style = getComputedStyle(node);
      for (const property of properties) {
        const value = [
          "fill",
          "stroke",
          "stop-color",
          "flood-color",
          "lighting-color",
        ].includes(property)
          ? this.#svgPaintValue(style, property)
          : style.getPropertyValue(property);
        if (value)
          /** @type {HTMLElement | SVGElement} */
          (target).style.setProperty(property, value);
      }
    });
    return new XMLSerializer().serializeToString(clone);
  };
  /**
   * Derive svg vector elements for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @returns {SceneSvgVector[]} Captured svgVectorElements evidence for the calling operation.
   */
  static #svgVectorElements = svg => {
    const rootRect = svg.getBoundingClientRect();
    return [
      ...svg.querySelectorAll(
        "path,rect,circle,ellipse,line,polyline,polygon,text,use",
      ),
    ]
      .filter(node => this.#isRendered(node, 0.001))
      .map(node => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        const fill = this.#svgPaintValue(style, "fill");
        const stroke = this.#svgPaintValue(style, "stroke");
        return {
          tag: node.tagName.toLowerCase(),
          frameInSvg: this.#frame(rect, rootRect),
          fill: this.#colorDescriptor(this.#parseColor(fill)),
          stroke: this.#colorDescriptor(this.#parseColor(stroke)),
          paint: {
            fill: {
              raw: style.fill,
              resolved: fill,
              paintServer: /^url\(/i.test(fill) ? fill : null,
            },
            stroke: {
              raw: style.stroke,
              resolved: stroke,
              paintServer: /^url\(/i.test(stroke) ? stroke : null,
            },
            color: style.color,
          },
          strokeWidthRelativeToSvg: this.#ratio(
            parseFloat(style.strokeWidth) || 0,
            Math.max(1, Math.min(rootRect.width, rootRect.height)),
          ),
          strokeDashArrayRelativeToSvg:
            style.strokeDasharray && style.strokeDasharray !== "none"
              ? style.strokeDasharray
                  .split(/[ ,]+/)
                  .filter(Boolean)
                  .map(value =>
                    this.#cssLengthRatio(
                      value,
                      Math.max(1, Math.min(rootRect.width, rootRect.height)),
                    ),
                  )
              : [],
          strokeLineCap: style.strokeLinecap,
          strokeLineJoin: style.strokeLinejoin,
          opacity: this.#effectiveOpacity(node),
          text:
            node instanceof globalThis.SVGTextElement ? node.textContent : null,
        };
      });
  };
  /**
   * Derive is svg icon for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {boolean} Captured isSvgIcon evidence for the calling operation.
   */
  static #isSvgIcon = (svg, rect, context) => {
    if (rect.width <= 0 || rect.height <= 0) return false;
    const width = this.#ratio(rect.width, context.rootRect.width);
    const height = this.#ratio(rect.height, context.rootRect.height);
    const area = width * height;
    const explicitHint =
      svg.matches(
        '[role="img"], [aria-hidden="true"], [data-icon], .icon, [class*="icon" i]',
      ) || Boolean(svg.querySelector("use"));
    const compactSize =
      width <= context.settings.iconMaxWidthFraction &&
      height <= context.settings.iconMaxHeightFraction &&
      area <= context.settings.iconMaxAreaFraction;
    return (
      compactSize ||
      (explicitHint && area <= context.settings.iconMaxAreaFraction * 2)
    );
  };
  /**
   * Derive icon primitive for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {SceneMeta} meta Shared source identity and normalized primitive metadata.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {Promise<SceneObject>} Captured iconPrimitive evidence for the calling operation.
   */
  static #iconPrimitive = async (svg, style, meta, context) => {
    const raster = await this.#rasterizeMedia(svg, style, meta, {
      ...context,
      settings: {
        ...context.settings,
        gridColumns: context.settings.iconGridColumns,
        gridRows: context.settings.iconGridRows,
      },
    });
    const styledMarkup = this.#serializeStyledSvg(svg)
      .replace(/>\s+</g, "><")
      .trim();
    let fingerprint = 2166136261;
    for (let index = 0; index < styledMarkup.length; index++) {
      fingerprint ^= styledMarkup.charCodeAt(index);
      fingerprint = Math.imul(fingerprint, 16777619);
    }
    const assetId = `svg-icon-${(fingerprint >>> 0).toString(36)}`;
    if (!context.iconAssets.has(assetId)) {
      const vectors = this.#svgVectorElements(svg);
      const primitiveTypes = Object.fromEntries(
        [...new Set(vectors.map(({ tag }) => tag))].map(tag => [
          tag,
          vectors.filter(item => item.tag === tag).length,
        ]),
      );
      const colors = [
        ...vectors
          .reduce(
            (
              /** @type {Map<string, SceneColorDescriptor>} */ result,
              vector,
            ) => {
              for (const color of [vector.fill, vector.stroke])
                if (color?.hex && color.rgba[3] > 0)
                  result.set(`${color.hex}:${color.rgba[3]}`, color);
              return result;
            },
            /** @type {Map<string, SceneColorDescriptor>} */
            (new Map()),
          )
          .values(),
      ].slice(0, 12);
      context.iconAssets.set(assetId, {
        id: assetId,
        type: "svg-icon",
        viewBox: svg.getAttribute("viewBox"),
        aspectRatio: svg.getBoundingClientRect().height
          ? this.#round(
              svg.getBoundingClientRect().width /
                svg.getBoundingClientRect().height,
            )
          : null,
        primitiveCount: vectors.length,
        primitiveTypes,
        semanticHint: this.#svgIconSemantics(svg),
        colors,
        strokeSummary: this.#svgStrokeSummary(svg),
        averageColor: raster?.stats?.averageColor ?? null,
        averageContrast: raster?.stats?.averageContrast ?? null,
        colorGrid: raster?.stats?.grid ?? [],
        colorGridDefinition: raster?.stats?.gridDefinition ?? null,
        colorGridContrast: raster?.stats?.gridContrast ?? null,
        colorRegions: raster?.stats?.regions ?? [],
        colorRegionDefinition: raster?.stats?.regionDefinition ?? null,
        markup: context.settings.includeIconMarkup ? styledMarkup : null,
        binary: context.settings.includeIconBinary
          ? (raster?.binary ?? null)
          : null,
        accuracy: raster?.accuracy ?? "vector-summary-only",
      });
    }
    const semantics = this.#svgIconSemantics(svg);
    return {
      ...meta,
      id: this.#nextObjectId(context, "icon"),
      type: "icon",
      assetRef: assetId,
      semantics,
      appearance: {
        opacity: Number(style.opacity),
        effectiveOpacity: meta.visibility.effectiveOpacity,
        mixBlendMode: style.mixBlendMode,
        filter: style.filter === "none" ? null : style.filter,
      },
    };
  };
  /**
   * Derive svg icon semantics for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @returns {SceneRecord} Captured svgIconSemantics evidence for the calling operation.
   */
  static #svgIconSemantics = svg => {
    const title =
      svg.querySelector(":scope > title")?.textContent?.trim() || null;
    const use = svg.querySelector("use");
    const symbolReference =
      use?.getAttribute("href") || use?.getAttribute("xlink:href") || null;
    const dataName =
      svg.getAttribute("data-icon") ||
      svg.getAttribute("data-lucide") ||
      svg.getAttribute("data-feather") ||
      svg.getAttribute("data-testid") ||
      null;
    const classHint =
      [...svg.classList].find(name =>
        /(?:^|[-_])(icon|ico)(?:[-_]|$)/i.test(name),
      ) ||
      [...svg.classList].find(name =>
        /(chevron|arrow|close|menu|search|edit|delete|trash|plus|minus|check|settings|info|warning|user|home|play|pause)/i.test(
          name,
        ),
      ) ||
      null;
    const rawName =
      svg.getAttribute("aria-label") ||
      title ||
      dataName ||
      symbolReference?.replace(/^#/, "") ||
      classHint;
    return {
      name: rawName || null,
      label: svg.getAttribute("aria-label") || title,
      title,
      symbolReference,
      sourceHint: dataName || classHint,
      decorative: svg.getAttribute("aria-hidden") === "true",
    };
  };
  /**
   * Derive svg stroke summary for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @returns {SceneRecord[] | null} Captured svgStrokeSummary evidence for the calling operation.
   */
  static #svgStrokeSummary = svg => {
    const rootRect = svg.getBoundingClientRect();
    const strokes = [
      ...svg.querySelectorAll(
        "path,line,polyline,polygon,rect,circle,ellipse,use",
      ),
    ]
      .filter(node => this.#isRendered(node, 0.001))
      .map(node => {
        const style = getComputedStyle(node);
        const width = parseFloat(style.strokeWidth) || 0;
        const strokeBase = Math.max(
          1,
          Math.min(rootRect.width, rootRect.height),
        );
        const dashArray =
          style.strokeDasharray && style.strokeDasharray !== "none"
            ? style.strokeDasharray.split(/[ ,]+/).filter(Boolean)
            : [];
        return {
          style: dashArray.length ? "dashed" : "solid",
          widthRelativeToSvg: this.#ratio(width, strokeBase),
          dashPatternRelativeToSvg: dashArray.map(value =>
            this.#cssLengthRatio(value, strokeBase),
          ),
          dashOffsetRelativeToSvg: this.#ratio(
            parseFloat(style.strokeDashoffset) || 0,
            strokeBase,
          ),
          lineCap: style.strokeLinecap,
          lineJoin: style.strokeLinejoin,
        };
      })
      .filter(({ widthRelativeToSvg }) => widthRelativeToSvg > 0);
    if (!strokes.length) return null;
    /** @type {Map<string, SceneRecord & {count: number}>} */
    const signatures = new Map();
    for (const stroke of strokes) {
      const key = JSON.stringify(stroke);
      const existing = signatures.get(key);
      if (existing) existing.count++;
      else
        signatures.set(key, {
          ...stroke,
          count: 1,
        });
    }
    return [...signatures.values()];
  };
  /**
   * Derive svg image for the current rendered scene.
   * @param {Element} svg Svg used by this operation.
   * @returns {Promise<HTMLImageElement>} Captured svgImage evidence for the calling operation.
   */
  static #svgImage = async svg => {
    const source = this.#serializeStyledSvg(svg);
    const blob = new Blob([source], {
      type: "image/svg+xml;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    try {
      const image = new Image();
      image.decoding = "async";
      image.src = url;
      await image.decode();
      return image;
    } finally {
      URL.revokeObjectURL(url);
    }
  };
  /**
   * Derive object fit rect for the current rendered scene.
   * @param {number} intrinsicWidth Intrinsicwidth used by this operation.
   * @param {number} intrinsicHeight Intrinsicheight used by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {string} objectFit Objectfit used by this operation.
   * @param {string} objectPosition Objectposition used by this operation.
   * @returns {{left:number,top:number,width:number,height:number}} Captured objectFitRect evidence for the calling operation.
   */
  static #objectFitRect = (
    intrinsicWidth,
    intrinsicHeight,
    rect,
    objectFit,
    objectPosition,
  ) => {
    const fit = objectFit || "fill";
    let width = rect.width;
    let height = rect.height;
    if (fit !== "fill") {
      let scale =
        fit === "cover"
          ? Math.max(rect.width / intrinsicWidth, rect.height / intrinsicHeight)
          : Math.min(
              rect.width / intrinsicWidth,
              rect.height / intrinsicHeight,
            );
      if (fit === "scale-down") scale = Math.min(1, scale);
      if (fit === "none") scale = 1;
      width = intrinsicWidth * scale;
      height = intrinsicHeight * scale;
    }
    const position = this.#parseObjectPosition(objectPosition);
    return {
      left: rect.left + (rect.width - width) * position.x,
      top: rect.top + (rect.height - height) * position.y,
      width,
      height,
    };
  };
  /**
   * Derive parse object position for the current rendered scene.
   * @param {string} [value] Value read from the current DOM, configuration or serialized scene.
   * @returns {ScenePoint} Captured parseObjectPosition evidence for the calling operation.
   */
  static #parseObjectPosition = (value = "50% 50%") => {
    const parts = value.trim().split(/\s+/);
    /**
     * Derive parse for the current rendered scene.
     * @param {string | undefined} part Part used by this operation.
     * @param {string} axis Axis used by this operation.
     * @returns {number} Parsed transform component.
     */
    const parse = (part, axis) => {
      if (!part) return 0.5;
      const keywords = /** @type {Record<string, number>} */ (
        axis === "x"
          ? {
              left: 0,
              center: 0.5,
              right: 1,
            }
          : {
              top: 0,
              center: 0.5,
              bottom: 1,
            }
      );
      if (part in keywords) return keywords[part] ?? 0.5;
      if (part.endsWith("%")) return this.#clamp(parseFloat(part) / 100, 0, 1);
      return 0.5;
    };
    return {
      x: parse(parts[0], "x"),
      y: parse(parts[1] ?? "50%", "y"),
    };
  };
  /**
   * Derive visible rect for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {DOMRectReadOnly} rootRect Rootrect used by this operation.
   * @returns {SceneRect} Captured visibleRect evidence for the calling operation.
   */
  static #visibleRect = (element, rect, rootRect) => {
    let visible = this.#intersectionRect(rect, {
      left: Math.max(0, rootRect.left),
      top: Math.max(0, rootRect.top),
      right: Math.min(innerWidth, rootRect.right),
      bottom: Math.min(innerHeight, rootRect.bottom),
      width: Math.max(
        0,
        Math.min(innerWidth, rootRect.right) - Math.max(0, rootRect.left),
      ),
      height: Math.max(
        0,
        Math.min(innerHeight, rootRect.bottom) - Math.max(0, rootRect.top),
      ),
    });
    for (
      let ancestor = element.parentElement;
      ancestor;
      ancestor = ancestor.parentElement
    ) {
      const style = getComputedStyle(ancestor);
      const clipsX = ["hidden", "clip", "scroll", "auto"].includes(
        style.overflowX,
      );
      const clipsY = ["hidden", "clip", "scroll", "auto"].includes(
        style.overflowY,
      );
      if (!clipsX && !clipsY) continue;
      const ancestorRect = ancestor.getBoundingClientRect();
      const clipped = {
        left: clipsX ? Math.max(visible.left, ancestorRect.left) : visible.left,
        right: clipsX
          ? Math.min(visible.right, ancestorRect.right)
          : visible.right,
        top: clipsY ? Math.max(visible.top, ancestorRect.top) : visible.top,
        bottom: clipsY
          ? Math.min(visible.bottom, ancestorRect.bottom)
          : visible.bottom,
      };
      visible = {
        ...clipped,
        width: Math.max(0, clipped.right - clipped.left),
        height: Math.max(0, clipped.bottom - clipped.top),
      };
    }
    return visible;
  };
  /**
   * Check display, visibility, opacity and geometry before traversing a node.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {number} opacityThreshold Opacitythreshold used by this operation.
   * @returns {boolean} Captured isRendered evidence for the calling operation.
   */
  static #isRendered = (element, opacityThreshold) => {
    const style = getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.visibility === "collapse" ||
      this.#effectiveOpacity(element) <= opacityThreshold
    )
      return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  /**
   * Derive effective opacity for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {number} Captured effectiveOpacity evidence for the calling operation.
   */
  static #effectiveOpacity = element => {
    let opacity = 1;
    /** @type {Element | null} */
    let current = element;
    for (; current; current = current.parentElement)
      opacity *= Number(getComputedStyle(current).opacity);
    return this.#round(opacity);
  };
  /**
   * Derive border side for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {string} suffix Suffix used by this operation.
   * @returns {SceneBorderSide} Captured borderSide evidence for the calling operation.
   */
  static #borderSide = (style, suffix) => ({
    width:
      parseFloat(
        style.getPropertyValue(`border-${suffix.toLowerCase()}-width`),
      ) || 0,
    style: style.getPropertyValue(`border-${suffix.toLowerCase()}-style`),
    color: this.#parseColor(
      style.getPropertyValue(`border-${suffix.toLowerCase()}-color`),
    ),
  });
  /**
   * Derive radius for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @returns {SceneRadius} Captured radius evidence for the calling operation.
   */
  static #radius = (style, rect) => {
    /**
     * Derive corner for the current rendered scene.
     * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
     * @returns {ScenePoint} Corner radius fractions.
     */
    const corner = value => {
      const [horizontal = "0", vertical = horizontal] = String(value)
        .trim()
        .split(/\s+/);
      return {
        x: this.#cssLengthRatio(horizontal, Math.max(1, rect.width)),
        y: this.#cssLengthRatio(vertical, Math.max(1, rect.height)),
      };
    };
    const corners = {
      topLeft: corner(style.borderTopLeftRadius),
      topRight: corner(style.borderTopRightRadius),
      bottomRight: corner(style.borderBottomRightRadius),
      bottomLeft: corner(style.borderBottomLeftRadius),
    };
    const values = Object.values(corners);
    return {
      ...corners,
      rounded: values.some(({ x, y }) => x > 0 || y > 0),
      uniform: values.every(
        ({ x, y }) =>
          Math.abs(x - (values[0]?.x ?? 0)) <= 0.001 &&
          Math.abs(y - (values[0]?.y ?? 0)) <= 0.001,
      ),
    };
  };
  /**
   * Derive shape descriptor for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @returns {SceneRecord} Captured shape description evidence for the calling operation.
   */
  static #shapeDescriptor = (style, rect) => {
    const radius = this.#radius(style, rect);
    const corners = [
      radius.topLeft,
      radius.topRight,
      radius.bottomRight,
      radius.bottomLeft,
    ];
    const fullyRoundedX = corners.every(({ x }) => x >= 0.49);
    const fullyRoundedY = corners.every(({ y }) => y >= 0.49);
    const aspect = rect.height ? rect.width / rect.height : 0;
    const kind =
      fullyRoundedX && fullyRoundedY && Math.abs(aspect - 1) <= 0.05
        ? "circle"
        : (fullyRoundedX || fullyRoundedY) && radius.uniform
          ? "pill"
          : radius.rounded
            ? "rounded-rectangle"
            : "rectangle";
    return {
      kind,
      radius,
    };
  };
  /**
   * Derive css stroke descriptor for the current rendered scene.
   * @param {string} style Border style keyword used by this operation.
   * @param {number} width Width used by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {string} side Side used by this operation.
   * @returns {SceneRecord} Captured cssStroke description evidence for the calling operation.
   */
  static #cssStrokeDescriptor = (style, width, rect, side) => {
    const horizontal =
      side === "top" || side === "bottom" || side === "outline";
    const length = horizontal
      ? Math.max(1, rect.width)
      : Math.max(1, rect.height);
    const thickness = Math.max(1e-9, width);
    const pattern = {
      solid: {
        kind: "solid",
      },
      dashed: {
        kind: "dashed",
        dashToThickness: "browser-defined",
        estimatedSegmentCount: Math.max(
          1,
          Math.round(length / (thickness * 6)),
        ),
      },
      dotted: {
        kind: "dotted",
        dotDiameterToThickness: 1,
        estimatedDotCount: Math.max(1, Math.round(length / (thickness * 2))),
      },
      double: {
        kind: "double",
        layers: 2,
      },
      groove: {
        kind: "3d-groove",
      },
      ridge: {
        kind: "3d-ridge",
      },
      inset: {
        kind: "3d-inset",
      },
      outset: {
        kind: "3d-outset",
      },
    }[style] ?? {
      kind: style || "unknown",
    };
    return {
      pattern,
      thicknessRelativeToLength: this.#ratio(width, length),
    };
  };
  /**
   * Derive border edge geometry for the current rendered scene.
   * @param {string} side Side used by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @returns {SceneRecord|null} Captured borderEdgeGeometry evidence for the calling operation.
   */
  static #borderEdgeGeometry = (side, style, rect) => {
    const radius = this.#radius(style, rect);
    const corners = {
      top: [radius.topLeft, radius.topRight],
      right: [radius.topRight, radius.bottomRight],
      bottom: [radius.bottomLeft, radius.bottomRight],
      left: [radius.topLeft, radius.bottomLeft],
    }[side];
    if (!corners) return null;
    const [startCorner, endCorner] = corners;
    if (!startCorner || !endCorner) return null;
    const axis = side === "top" || side === "bottom" ? "x" : "y";
    return {
      followsRoundedCorners: corners.some(corner => corner[axis] > 0),
      startRadius: startCorner[axis],
      endRadius: endCorner[axis],
    };
  };
  /**
   * Derive typography for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {DOMRectReadOnly} referenceRect Referencerect used by this operation.
   * @returns {SceneRecord} Captured typography evidence for the calling operation.
   */
  static #typography = (style, rect, referenceRect) => {
    const fontSize = Math.max(1e-9, parseFloat(style.fontSize) || 0);
    const weightNumber = Number(style.fontWeight);
    const decorationColor = this.#parseColor(style.textDecorationColor);
    const decorationThickness =
      style.textDecorationThickness === "auto" ||
      style.textDecorationThickness === "from-font"
        ? style.textDecorationThickness
        : this.#cssLengthRatio(style.textDecorationThickness, fontSize);
    return {
      family: style.fontFamily,
      sizeRelativeToBoxHeight: this.#ratio(fontSize, Math.max(1, rect.height)),
      sizeRelativeToReferenceHeight: this.#ratio(
        fontSize,
        Math.max(1, referenceRect?.height ?? rect.height),
      ),
      weight: style.fontWeight,
      weightClass: Number.isFinite(weightNumber)
        ? weightNumber >= 700
          ? "bold"
          : weightNumber >= 600
            ? "semibold"
            : weightNumber <= 300
              ? "light"
              : "regular"
        : style.fontWeight,
      style: style.fontStyle,
      stretch: style.fontStretch,
      variant: style.fontVariant,
      kerning: style.fontKerning,
      opticalSizing: style.fontOpticalSizing,
      featureSettings:
        style.fontFeatureSettings === "normal"
          ? null
          : style.fontFeatureSettings,
      variationSettings:
        style.fontVariationSettings === "normal"
          ? null
          : style.fontVariationSettings,
      lineHeightRelativeToFont:
        style.lineHeight === "normal"
          ? null
          : this.#ratio(parseFloat(style.lineHeight), fontSize),
      letterSpacingRelativeToFont:
        style.letterSpacing === "normal"
          ? 0
          : this.#ratio(parseFloat(style.letterSpacing), fontSize),
      wordSpacingRelativeToFont:
        style.wordSpacing === "normal"
          ? 0
          : this.#ratio(parseFloat(style.wordSpacing), fontSize),
      align: style.textAlign,
      direction: style.direction,
      writingMode: style.writingMode,
      transform: style.textTransform,
      indentRelativeToBoxWidth: this.#cssLengthRatio(
        style.textIndent,
        Math.max(1, rect.width),
      ),
      decoration: {
        lines:
          style.textDecorationLine === "none"
            ? []
            : style.textDecorationLine.split(/\s+/).filter(Boolean),
        style: style.textDecorationStyle,
        color: this.#colorDescriptor(decorationColor),
        thicknessRelativeToFont: decorationThickness,
        underlineOffsetRelativeToFont:
          style.textUnderlineOffset === "auto"
            ? "auto"
            : this.#cssLengthRatio(style.textUnderlineOffset, fontSize),
        underlinePosition: style.textUnderlinePosition,
        skipInk: style.textDecorationSkipInk,
      },
      emphasisMarks: {
        style:
          style.textEmphasisStyle && style.textEmphasisStyle !== "none"
            ? style.textEmphasisStyle
            : null,
        color: this.#colorDescriptor(this.#parseColor(style.textEmphasisColor)),
        position: style.textEmphasisPosition || null,
      },
      emphasis: {
        italic:
          style.fontStyle === "italic" || style.fontStyle.startsWith("oblique"),
        bold: Number.isFinite(weightNumber) && weightNumber >= 600,
        uppercase: style.textTransform === "uppercase",
        smallCaps: String(style.fontVariantCaps).includes("small-caps"),
      },
      stroke: {
        widthRelativeToFont: this.#cssLengthRatio(
          style.webkitTextStrokeWidth || "0",
          fontSize,
        ),
        color: this.#colorDescriptor(
          this.#parseColor(style.webkitTextStrokeColor),
        ),
      },
      shadow: style.textShadow === "none" ? null : style.textShadow,
      lineClamp:
        style.webkitLineClamp && style.webkitLineClamp !== "none"
          ? Number(style.webkitLineClamp) || style.webkitLineClamp
          : null,
    };
  };
  /**
   * Derive backdrop filter for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @returns {string|null} Captured backdropFilter evidence for the calling operation.
   */
  static #backdropFilter = style => {
    const value =
      style.backdropFilter ||
      style.getPropertyValue("-webkit-backdrop-filter") ||
      "none";
    return value === "none" ? null : value;
  };
  /**
   * Derive transform chain for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {?Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} rootRect Rootrect used by this operation.
   * @returns {SceneRecord[]} Captured transformChain evidence for the calling operation.
   */
  static #transformChain = (element, rootRect) => {
    /** @type {SceneRecord[]} */
    const chain = [];
    for (
      let current = /** @type {Element|null} */ (element);
      current instanceof Element;
      current = current.parentElement
    ) {
      const style = getComputedStyle(current);
      const transform = this.#matrixDescriptor(style.transform, rootRect);
      const individual = this.#individualTransformDescriptor(style);
      const perspective =
        style.perspective !== "none" ? style.perspective : null;
      if (transform || Object.values(individual).some(Boolean) || perspective)
        chain.unshift({
          selector: this.#selectElement(current),
          transform,
          individual,
          transformOrigin: style.transformOrigin,
          transformBox: style.transformBox,
          perspective,
          perspectiveOrigin: style.perspectiveOrigin,
        });
    }
    return chain;
  };
  /**
   * Derive transform descriptor for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {DOMRectReadOnly} parentRect Parentrect used by this operation.
   * @param {DOMRectReadOnly} rootRect Rootrect used by this operation.
   * @returns {SceneRecord} Captured transform description evidence for the calling operation.
   */
  static #transformDescriptor = (
    element,
    style,
    rect,
    parentRect,
    rootRect,
  ) => {
    const quad = this.#quadDescriptor(element, rect, rootRect);
    const own = this.#matrixDescriptor(style.transform, rootRect);
    const individual = this.#individualTransformDescriptor(style);
    const layoutWidth =
      element instanceof HTMLElement && !(element instanceof SVGElement)
        ? element.offsetWidth || rect.width
        : rect.width;
    const layoutHeight =
      element instanceof HTMLElement && !(element instanceof SVGElement)
        ? element.offsetHeight || rect.height
        : rect.height;
    return {
      transformed: Boolean(
        own ||
        Object.values(individual).some(Boolean) ||
        this.#transformChain(element.parentElement, rootRect).length,
      ),
      own,
      individual,
      origin: style.transformOrigin,
      box: style.transformBox,
      chain: this.#transformChain(element, rootRect),
      finalQuad: quad,
      finalAxisAlignedFrame: this.#frame(rect, rootRect),
      layoutSizeBeforeOwnTransform: {
        width: this.#ratio(layoutWidth, parentRect.width),
        height: this.#ratio(layoutHeight, parentRect.height),
      },
      effect: {
        axisAlignedWidthScale: layoutWidth
          ? this.#round(rect.width / layoutWidth)
          : null,
        axisAlignedHeightScale: layoutHeight
          ? this.#round(rect.height / layoutHeight)
          : null,
        paintedAreaScale:
          layoutWidth && layoutHeight
            ? this.#round(
                quad.area * rootRect.width * rootRect.height /
                  (layoutWidth * layoutHeight),
              )
            : null,
        finalCenter: quad.center,
        finalRotationDegrees: quad.orientationDegrees,
        cornerAngleDegrees: quad.cornerAngleDegrees,
        axisAlignedBoundingBox: this.#frame(rect, rootRect),
        changesVisualPosition: Boolean(
          individual.translate ||
          own?.translation?.x ||
          own?.translation?.y ||
          quad.orientationDegrees ||
          style.transformOrigin !== "50% 50%",
        ),
        changesVisualSize:
          Math.abs((layoutWidth ? rect.width / layoutWidth : 1) - 1) > 0.001 ||
          Math.abs((layoutHeight ? rect.height / layoutHeight : 1) - 1) > 0.001,
        note: "Final quad is authoritative for visual geometry. Size/position effects include ancestor transforms; own matrix describes this element's declared computed transform.",
      },
    };
  };
  /**
   * Derive top layer state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneTopLayerState} Captured topLayerState evidence for the calling operation.
   */
  static #topLayerState = element => {
    let modal = false;
    let popover = false;
    try {
      modal = element.matches(":modal");
    } catch {
      // Older browsers may not implement :modal; retain false.
    }
    try {
      popover = element.matches(":popover-open");
    } catch {
      // Older browsers may not implement :popover-open; retain false.
    }
    return {
      active: modal || popover || document.fullscreenElement === element,
      modal,
      popover,
      fullscreen: document.fullscreenElement === element,
    };
  };
  /**
   * Derive stacking context reasons for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @returns {string[]} Captured stackingContextReasons evidence for the calling operation.
   */
  static #stackingContextReasons = (element, style) => {
    const reasons = [];
    const parentStyle = element.parentElement
      ? getComputedStyle(element.parentElement)
      : null;
    const positioned = ["absolute", "relative", "fixed", "sticky"].includes(
      style.position,
    );
    const zIndex = style.zIndex !== "auto";
    const topLayer = this.#topLayerState(element);
    if (!element.parentElement) reasons.push("document-root");
    if (topLayer.active)
      reasons.push(
        `top-layer:${topLayer.modal ? "modal" : topLayer.popover ? "popover" : "fullscreen"}`,
      );
    if (["fixed", "sticky"].includes(style.position))
      reasons.push(style.position);
    if (positioned && zIndex) reasons.push("positioned-with-z-index");
    if (
      parentStyle &&
      ["flex", "inline-flex", "grid", "inline-grid"].includes(
        parentStyle.display,
      ) &&
      zIndex
    )
      reasons.push("flex-or-grid-item-with-z-index");
    if (Number(style.opacity) < 1) reasons.push("opacity");
    if (style.mixBlendMode !== "normal") reasons.push("mix-blend-mode");
    if (style.transform !== "none") reasons.push("transform");
    if (style.translate && style.translate !== "none")
      reasons.push("translate");
    if (style.rotate && style.rotate !== "none") reasons.push("rotate");
    if (style.scale && style.scale !== "none") reasons.push("scale");
    if (style.filter !== "none") reasons.push("filter");
    if (this.#backdropFilter(style)) reasons.push("backdrop-filter");
    if (style.perspective !== "none") reasons.push("perspective");
    if (style.clipPath !== "none") reasons.push("clip-path");
    if (style.maskImage !== "none") reasons.push("mask");
    if (style.isolation === "isolate") reasons.push("isolation");
    if (style.containerType && style.containerType !== "normal")
      reasons.push(`container-type:${style.containerType}`);
    if (/(?:paint|layout|strict|content)/.test(style.contain))
      reasons.push(`contain:${style.contain}`);
    if (
      /(?:transform|opacity|filter|perspective|clip-path|mask)/.test(
        style.willChange,
      )
    )
      reasons.push(`will-change:${style.willChange}`);
    return reasons;
  };
  /**
   * Derive stacking context chain for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord[]} Captured stackingContextChain evidence for the calling operation.
   */
  static #stackingContextChain = element => {
    /** @type {SceneRecord[]} */
    const chain = [];
    for (
      let current = /** @type {Element|null} */ (element);
      current instanceof Element;
      current = current.parentElement
    ) {
      const style = getComputedStyle(current);
      const reasons = this.#stackingContextReasons(current, style);
      if (reasons.length)
        chain.unshift({
          selector: this.#selectElement(current),
          zIndex: style.zIndex,
          numericZIndex: style.zIndex === "auto" ? null : Number(style.zIndex),
          position: style.position,
          topLayer: this.#topLayerState(current),
          reasons,
        });
    }
    return chain;
  };
  /**
   * Derive local paint layer for the current rendered scene.
   * @param {string} type Type used by this operation.
   * @param {?string} [source] Source used by this operation.
   * @returns {number} Captured localPaintLayer evidence for the calling operation.
   */
  static #localPaintLayer = (type, source = null) => {
    if (type === "shadow") return 5;
    if (type === "surface") return 10;
    if (type === "contour" && source === "border") return 20;
    if (type === "line") return 20;
    if (["image", "svg", "icon"].includes(type)) return 30;
    if (type === "control") return 35;
    if (type === "text") return 40;
    if (type === "decoration") return 50;
    if (type === "contour" && source === "outline") return 90;
    return 45;
  };
  /**
   * Derive layering descriptor for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @returns {SceneRecord} Captured layering description evidence for the calling operation.
   */
  static #layeringDescriptor = (element, style) => {
    const reasons = this.#stackingContextReasons(element, style);
    return {
      position: style.position,
      zIndex: style.zIndex,
      numericZIndex: style.zIndex === "auto" ? null : Number(style.zIndex),
      isolation: style.isolation,
      topLayer: this.#topLayerState(element),
      createsStackingContext: reasons.length > 0,
      stackingContextReasons: reasons,
      stackingContextChain: this.#stackingContextChain(element),
      selector: this.#selectElement(element),
      paintOrderBasis: "css-stacking-context-plus-overlap-hit-test",
    };
  };
  /**
   * Derive hit test polygon samples for the current rendered scene.
   * @param {Array<{x: number, y: number}>} polygon Polygon used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneHitSample[]} Captured hitTestPolygonSamples evidence for the calling operation.
   */
  static #hitTestPolygonSamples = (polygon, context) => {
    const center = {
      x: polygon.reduce((sum, point) => sum + point.x, 0) / polygon.length,
      y: polygon.reduce((sum, point) => sum + point.y, 0) / polygon.length,
    };
    const normalized = [
      center,
      ...polygon.map(point => ({
        x: point.x * 0.82 + center.x * 0.18,
        y: point.y * 0.82 + center.y * 0.18,
      })),
      ...polygon.map((point, index) => {
        const next = polygon[(index + 1) % polygon.length] ?? point;
        return {
          x: (point.x + next.x) / 2 * 0.9 + center.x * 0.1,
          y: (point.y + next.y) / 2 * 0.9 + center.y * 0.1,
        };
      }),
    ];
    return normalized
      .map(point => ({
        normalized: {
          x: this.#round(point.x, 6),
          y: this.#round(point.y, 6),
        },
        x: context.rootRect.left + point.x * context.rootRect.width,
        y: context.rootRect.top + point.y * context.rootRect.height,
      }))
      .filter(
        ({ x, y }, index, points) =>
          x >= 0 &&
          y >= 0 &&
          x <= innerWidth &&
          y <= innerHeight &&
          points.findIndex(
            ({ x: px, y: py }) =>
              Math.abs(px - x) < 0.5 && Math.abs(py - y) < 0.5,
          ) === index,
      );
  };
  /**
   * Derive paint phase for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {ScenePaintPhase} Captured paintPhase evidence for the calling operation.
   */
  static #paintPhase = element => {
    const style = getComputedStyle(element);
    const z = style.zIndex === "auto" ? 0 : Number(style.zIndex);
    if (this.#topLayerState(element).active)
      return {
        group: 7,
        z: 0,
      };
    const positioned = ["absolute", "relative", "fixed", "sticky"].includes(
      style.position,
    );
    if (z < 0)
      return {
        group: 1,
        z,
      };
    if (style.float !== "none")
      return {
        group: 3,
        z,
      };
    if (
      !positioned &&
      /^(?:inline|inline-block|inline-flex|inline-grid)$/.test(style.display)
    )
      return {
        group: 4,
        z,
      };
    if (z > 0)
      return {
        group: 6,
        z,
      };
    if (positioned || this.#stackingContextReasons(element, style).length)
      return {
        group: 5,
        z,
      };
    return {
      group: 2,
      z,
    };
  };
  /**
   * Derive stacking context elements for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {Element[]} Captured stackingContextElements evidence for the calling operation.
   */
  static #stackingContextElements = element => {
    const chain = [];
    for (
      let current = /** @type {Element|null} */ (element);
      current instanceof Element;
      current = current.parentElement
    )
      if (
        this.#stackingContextReasons(current, getComputedStyle(current)).length
      )
        chain.unshift(current);
    if (chain.at(-1) !== element) chain.push(element);
    return chain;
  };
  /**
   * Derive modeled visual order for the current rendered scene.
   * @param {SceneObject} first First used by this operation.
   * @param {SceneObject} second Second used by this operation.
   * @param {?Element} firstElement Firstelement used by this operation.
   * @param {?Element} secondElement Secondelement used by this operation.
   * @returns {?SceneModeledOrder} Captured modeledVisualOrder evidence for the calling operation.
   */
  static #modeledVisualOrder = (first, second, firstElement, secondElement) => {
    if (!firstElement || !secondElement) return null;
    if (firstElement.contains(secondElement)) {
      const ancestorAbove =
        first.type === "contour" && first[String("sourceKind")] === "outline";
      return {
        top: ancestorAbove ? first : second,
        bottom: ancestorAbove ? second : first,
        reason: ancestorAbove
          ? "ancestor-outline-after-descendants"
          : "descendant-painted-over-ancestor-background-content-model",
      };
    }
    if (secondElement.contains(firstElement)) {
      const ancestorAbove =
        second.type === "contour" && second[String("sourceKind")] === "outline";
      return {
        top: ancestorAbove ? second : first,
        bottom: ancestorAbove ? first : second,
        reason: ancestorAbove
          ? "ancestor-outline-after-descendants"
          : "descendant-painted-over-ancestor-background-content-model",
      };
    }
    const firstChain = this.#stackingContextElements(firstElement);
    const secondChain = this.#stackingContextElements(secondElement);
    let index = 0;
    while (
      index < firstChain.length &&
      index < secondChain.length &&
      firstChain[index] === secondChain[index]
    )
      index++;
    const firstParticipant = firstChain[Math.min(index, firstChain.length - 1)];
    const secondParticipant =
      secondChain[Math.min(index, secondChain.length - 1)];
    if (
      !firstParticipant ||
      !secondParticipant ||
      firstParticipant === secondParticipant
    )
      return null;
    const firstPhase = this.#paintPhase(firstParticipant);
    const secondPhase = this.#paintPhase(secondParticipant);
    if (firstPhase.group !== secondPhase.group)
      return firstPhase.group > secondPhase.group
        ? {
            top: first,
            bottom: second,
            reason: "css-paint-phase",
          }
        : {
            top: second,
            bottom: first,
            reason: "css-paint-phase",
          };
    if (firstPhase.z !== secondPhase.z)
      return firstPhase.z > secondPhase.z
        ? {
            top: first,
            bottom: second,
            reason: "stacking-context-z-index",
          }
        : {
            top: second,
            bottom: first,
            reason: "stacking-context-z-index",
          };
    if (
      firstParticipant.parentElement === secondParticipant.parentElement &&
      firstParticipant.parentElement
    ) {
      const parentDisplay = getComputedStyle(
        firstParticipant.parentElement,
      ).display;
      if (
        ["flex", "inline-flex", "grid", "inline-grid"].includes(parentDisplay)
      ) {
        const firstOrder =
          Number(getComputedStyle(firstParticipant).order) || 0;
        const secondOrder =
          Number(getComputedStyle(secondParticipant).order) || 0;
        if (firstOrder !== secondOrder)
          return firstOrder > secondOrder
            ? {
                top: first,
                bottom: second,
                reason: "order-modified-document-paint-order",
              }
            : {
                top: second,
                bottom: first,
                reason: "order-modified-document-paint-order",
              };
      }
    }
    const position =
      firstParticipant.compareDocumentPosition(secondParticipant);
    if (position & Node.DOCUMENT_POSITION_FOLLOWING)
      return {
        top: second,
        bottom: first,
        reason: "same-phase-document-paint-order",
      };
    if (position & Node.DOCUMENT_POSITION_PRECEDING)
      return {
        top: first,
        bottom: second,
        reason: "same-phase-document-paint-order",
      };
    return null;
  };
  /**
   * Derive stack index for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element[]} stack Stack used by this operation.
   * @param {?Element} element Live DOM element observed or managed by this operation.
   * @returns {number} Captured stackIndex evidence for the calling operation.
   */
  static #stackIndex = (stack, element) => {
    if (!element) return -1;
    const direct = stack.indexOf(element);
    if (direct >= 0) return direct;
    return stack.findIndex(
      candidate =>
        candidate instanceof Element &&
        (element.contains(candidate) || candidate.contains(element)),
    );
  };
  /**
   * Resolve the pairwise paint order from overlap hit tests and stacking evidence.
   * @param {SceneObject} first First used by this operation.
   * @param {SceneObject} second Second used by this operation.
   * @param {ScenePoint[]} overlapPolygon Overlappolygon used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneVisualOrder} Captured visualOrder evidence for the calling operation.
   */
  static #visualOrder = (first, second, overlapPolygon, context) => {
    if (first.sourceElementId === second.sourceElementId) {
      const firstRank = this.#localPaintLayer(
        first.type,
        typeof first[String("sourceKind")] === "string"
          ? first[String("sourceKind")]
          : null,
      );
      const secondRank = this.#localPaintLayer(
        second.type,
        typeof second[String("sourceKind")] === "string"
          ? second[String("sourceKind")]
          : null,
      );
      const firstAbove = firstRank > secondRank;
      return {
        topObjectId:
          firstRank === secondRank ? null : firstAbove ? first.id : second.id,
        bottomObjectId:
          firstRank === secondRank ? null : firstAbove ? second.id : first.id,
        confidence: firstRank === secondRank ? "undetermined" : "high",
        basis: "same-element-internal-paint-layer",
        consensus: firstRank === secondRank ? 0 : 1,
        samples: {
          usable: 0,
          firstAbove: 0,
          secondAbove: 0,
          tied: 0,
          points: [],
        },
      };
    }
    const firstElement = this.#elementFromId(
      first.sourceElementId,
      context.root,
      context,
    );
    const secondElement = this.#elementFromId(
      second.sourceElementId,
      context.root,
      context,
    );
    let firstAbove = 0;
    let secondAbove = 0;
    let tied = 0;
    let usable = 0;
    const details = [];
    for (const { x, y, normalized } of this.#hitTestPolygonSamples(
      overlapPolygon,
      context,
    )) {
      const stack = document.elementsFromPoint(x, y);
      const firstIndex = this.#stackIndex(stack, firstElement);
      const secondIndex = this.#stackIndex(stack, secondElement);
      if (firstIndex < 0 || secondIndex < 0) continue;
      usable++;
      if (firstIndex < secondIndex) firstAbove++;
      else if (secondIndex < firstIndex) secondAbove++;
      else tied++;
      details.push({
        point: normalized,
        firstStackIndex: firstIndex,
        secondStackIndex: secondIndex,
      });
    }
    const sampledWinner =
      firstAbove === secondAbove
        ? null
        : firstAbove > secondAbove
          ? first
          : second;
    const sampledLoser =
      sampledWinner === first
        ? second
        : sampledWinner === second
          ? first
          : null;
    const consensus = usable ? Math.max(firstAbove, secondAbove) / usable : 0;
    const modeled = this.#modeledVisualOrder(
      first,
      second,
      firstElement,
      secondElement,
    );
    const winner = sampledWinner ?? modeled?.top ?? null;
    const loser = sampledLoser ?? modeled?.bottom ?? null;
    return {
      topObjectId: winner?.id ?? null,
      bottomObjectId: loser?.id ?? null,
      topElementRef: winner?.sourceElementId ?? null,
      bottomElementRef: loser?.sourceElementId ?? null,
      confidence: sampledWinner
        ? consensus >= 0.8
          ? "high"
          : consensus >= 0.6
            ? "medium"
            : "low"
        : modeled
          ? "medium-model"
          : "undetermined",
      basis: sampledWinner
        ? "multi-point-elementsFromPoint-consensus-inside-transformed-overlap"
        : modeled
          ? `css-stacking-model:${modeled.reason}`
          : "undetermined",
      consensus: this.#round(consensus),
      hitTestLimitation:
        !usable &&
        [firstElement, secondElement].some(
          element =>
            element && getComputedStyle(element).pointerEvents === "none",
        )
          ? "pointer-events-none-excluded-from-browser-hit-test;css-stack-model-used"
          : null,
      samples: {
        usable,
        firstAbove,
        secondAbove,
        tied,
        points: details,
      },
      stackingContextRefs: {
        first: first.sourceElementId,
        second: second.sourceElementId,
      },
    };
  };
  /**
   * Attach overlap and stacking relationships to captured scene objects.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @param {SceneRecord[]} relationships Relationships used by this operation.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {SceneRecord} Captured visualStack evidence for the calling operation.
   */
  static #visualStack = (context, relationships) => {
    const stackingContexts = [];
    for (const [elementRef, descriptor] of context.elementRegistry) {
      const element = this.#elementFromId(elementRef, context.root, context);
      if (!element) continue;
      const style = getComputedStyle(element);
      const reasons = this.#stackingContextReasons(element, style);
      if (!reasons.length && style.zIndex === "auto") continue;
      stackingContexts.push({
        elementRef,
        selector: descriptor[String("selector")],
        zIndex: style.zIndex,
        numericZIndex: style.zIndex === "auto" ? null : Number(style.zIndex),
        position: style.position,
        reasons,
        parentContext:
          this.#stackingContextChain(element).at(-2)?.[String("selector")] ??
          null,
      });
    }
    return {
      interpretation:
        "Declared z-index is local to a stacking context. For overlapping objects, relationships[].stack is the authoritative visual-order record when hit-test consensus is available.",
      stackingContexts,
      resolvedOverlapCount: relationships.filter(
        record =>
          /** @type {?SceneRecord} */
          (record[String("stack")])?.[String("topObjectId")],
      ).length,
      unresolvedOverlapCount: relationships.filter(
        record =>
          !
            /** @type {?SceneRecord} */ (record[String("stack")])?.[
              String("topObjectId")
            ]
          ,
      ).length,
    };
  };
  /**
   * Normalize a rectangle relative to the supplied reference rectangle.
   * @param {SceneRect} rect Measured rectangle in CSS pixels.
   * @param {SceneRect} reference Reference geometry for coordinate normalization.
   * @returns {SceneFrame} Captured frame evidence for the calling operation.
   */
  static #frame = (rect, reference) => ({
    x: this.#ratio(rect.left - reference.left, reference.width),
    y: this.#ratio(rect.top - reference.top, reference.height),
    width: this.#ratio(rect.width, reference.width),
    height: this.#ratio(rect.height, reference.height),
  });
  /**
   * Reconstruct absolute geometry from a normalized scene frame.
   * @param {SceneFrame} frame Frame used by this operation.
   * @param {DOMRectReadOnly} reference Reference geometry for coordinate normalization.
   * @returns {SceneRect} Captured rectFromFrame evidence for the calling operation.
   */
  static #rectFromFrame = (frame, reference) => {
    const left = reference.left + frame.x * reference.width;
    const top = reference.top + frame.y * reference.height;
    const width = frame.width * reference.width;
    const height = frame.height * reference.height;
    return {
      left,
      top,
      right: left + width,
      bottom: top + height,
      width,
      height,
    };
  };
  /**
   * Derive intersection rect for the current rendered scene.
   * @param {SceneRect} a A used by this operation.
   * @param {SceneRect} b B used by this operation.
   * @returns {SceneRect} Captured intersectionRect evidence for the calling operation.
   */
  static #intersectionRect = (a, b) => {
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    return {
      left,
      top,
      right,
      bottom,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top),
    };
  };
  /**
   * Derive frame intersection for the current rendered scene.
   * @param {SceneFrame} a A used by this operation.
   * @param {SceneFrame} b B used by this operation.
   * @returns {?SceneFrame} Captured frameIntersection evidence for the calling operation.
   */
  static #frameIntersection = (a, b) => {
    const left = Math.max(a.x, b.x);
    const top = Math.max(a.y, b.y);
    const right = Math.min(a.x + a.width, b.x + b.width);
    const bottom = Math.min(a.y + a.height, b.y + b.height);
    if (right <= left || bottom <= top) return null;
    return {
      x: this.#round(left),
      y: this.#round(top),
      width: this.#round(right - left),
      height: this.#round(bottom - top),
    };
  };
  /**
   * Derive next object id for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @param {string} prefix Prefix used by this operation.
   * @returns {string} Captured nextObjectId evidence for the calling operation.
   */
  static #nextObjectId = (context, prefix) => `${prefix}-${context.nextId++}`;
  /**
   * Derive register element for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {void} Updates the capture context in place.
   */
  static #registerElement = (element, context) => {
    const id = this.#elementId(element, context);
    if (context.elementRegistry.has(id)) return;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const parentRect =
      element.parentElement?.getBoundingClientRect() ?? context.rootRect;
    context.elementsById.set(id, element);
    context.elementRegistry.set(id, {
      ...this.#serializeElement(element, context),
      ...(context.settings.includeComputedStyle && {
        computedStyle: Object.fromEntries(
          [...style].map(property => [
            property,
            style.getPropertyValue(property),
          ]),
        ),
      }),
      visual: {
        frame: this.#frame(rect, context.rootRect),
        viewportFrame: {
          x: this.#round(rect.left),
          y: this.#round(rect.top),
          right: this.#round(rect.right),
          bottom: this.#round(rect.bottom),
          width: this.#round(rect.width),
          height: this.#round(rect.height),
        },
        documentFrame: {
          x: this.#round(rect.left + scrollX),
          y: this.#round(rect.top + scrollY),
          right: this.#round(rect.right + scrollX),
          bottom: this.#round(rect.bottom + scrollY),
          width: this.#round(rect.width),
          height: this.#round(rect.height),
        },
        transform: this.#transformDescriptor(
          element,
          style,
          rect,
          parentRect,
          context.rootRect,
        ),
        layering: this.#layeringDescriptor(element, style),
      },
    });
  };
  /**
   * Derive element screenshot frame for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {{parent:Element,rect:DOMRectReadOnly,parentRect:DOMRectReadOnly,x:number,y:number,frame:SceneRecord}} Captured elementScreenshotFrame evidence for the calling operation.
   */
  static #elementScreenshotFrame = element => {
    const parent = element.parentElement ?? element;
    const rect = element.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const x =
      rect.left -
      parentRect.left +
      (parent === element ? 0 : parent.scrollLeft);
    const y =
      rect.top - parentRect.top + (parent === element ? 0 : parent.scrollTop);
    return {
      parent,
      rect,
      parentRect,
      x,
      y,
      frame: {
        x: parentRect.width ? this.#round(x / parentRect.width) : 0,
        y: parentRect.height ? this.#round(y / parentRect.height) : 0,
        width: parentRect.width
          ? this.#round(rect.width / parentRect.width)
          : 1,
        height: parentRect.height
          ? this.#round(rect.height / parentRect.height)
          : 1,
      },
    };
  };
  /**
   * Derive screenshot visual signature for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} parentRect Parentrect used by this operation.
   * @param {number} x X used by this operation.
   * @param {number} y Y used by this operation.
   * @returns {string} Captured screenshotVisualSignature evidence for the calling operation.
   */
  static #screenshotVisualSignature = (element, parentRect, x, y) => {
    const style = getComputedStyle(element);
    return [
      element.outerHTML,
      parentRect.width,
      parentRect.height,
      x,
      y,
      element.clientWidth,
      element.clientHeight,
      style.cssText ||
        [
          style.display,
          style.position,
          style.width,
          style.height,
          style.transform,
          style.transformOrigin,
          style.opacity,
          style.background,
          style.border,
          style.borderRadius,
          style.boxShadow,
          style.color,
          style.font,
          style.filter,
          style.clipPath,
          style.overflow,
        ].join("\u001f"),
    ].join("\u001e");
  };
  /**
   * Rasterize an element in its parent coordinate frame and encode a PNG.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {SceneElementCaptureOptions} [options] Configuration for this operation; omitted fields use its declared defaults.
   * @returns {Promise<{data:string,blob:Blob,frame:SceneRecord}>} Captured captureElementInParentFrame evidence for the calling operation.
   */
  static #captureElementInParentFrame = async (element, options = {}) => {
    if (!(element instanceof Element))
      throw new TypeError("element must be an Element.");
    const htmlToImage = evidenceGlobal.htmlToImage;
    if (!htmlToImage?.toCanvas)
      throw new Error("htmlToImage.toCanvas is unavailable.");
    const { parent, rect, parentRect, frame, x, y } =
      this.#elementScreenshotFrame(element);
    if (rect.width <= 0 || rect.height <= 0)
      throw new Error("Element has no rendered area.");
    const mime =
      typeof options.mime === "string" &&
      ["image/png", "image/webp", "image/jpeg"].includes(options.mime)
        ? options.mime
        : "image/png";
    const quality = Math.max(0.1, Math.min(1, options.quality ?? 0.92));
    const pixelRatio = Math.max(
      0.1,
      Math.min(
        options.pixelRatio ?? 1,
        (options.maxDimension ?? Infinity) / Math.max(rect.width, rect.height),
      ),
    );
    const background =
      options.background === "computed"
        ? getComputedStyle(element).backgroundColor
        : ({
            white: "#fff",
            black: "#000",
          }[typeof options.background === "string" ? options.background : ""] ??
          null);
    const resolvedBackground =
      background && !["transparent", "rgba(0, 0, 0, 0)"].includes(background)
        ? background
        : mime === "image/jpeg"
          ? "#fff"
          : null;
    const signature = [
      mime,
      quality,
      pixelRatio,
      resolvedBackground,
      options.skipAutoScale ?? false,
      this.#screenshotVisualSignature(element, parentRect, x, y),
    ].join("\u001d");
    const cachedScreenshot = this.#screenshotCache.get(element);
    if (!options.fresh && cachedScreenshot?.[String("signature")] === signature)
      return cachedScreenshot[String("capture")];
    const source = await htmlToImage.toCanvas(element, {
      pixelRatio,
      skipAutoScale: options.skipAutoScale ?? false,
      width: rect.width,
      height: rect.height,
      style: {
        overflow: "hidden",
      },
    });
    const canvas = Object.assign(document.createElement("canvas"), {
      width: Math.max(1, Math.round(rect.width * pixelRatio)),
      height: Math.max(1, Math.round(rect.height * pixelRatio)),
    });
    const context = canvas.getContext("2d");
    if (!context) throw new Error("2D canvas context is unavailable.");
    resolvedBackground &&
      Object.assign(context, {
        fillStyle: resolvedBackground,
      }) &&
      context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => {
      canvas.toBlob(resolve, mime, quality);
    });
    if (!blob) throw new Error("Element screenshot could not be encoded.");
    const capture = {
      blob,
      data: await new Promise((resolve, reject) => {
        const reader = Object.assign(new FileReader(), {
          onerror: reject,
          /**
           * Resolve the current FileReader operation after its terminal event.
           * @returns {void} Updates the capture context in place.
           */
          onloadend: () => resolve(reader.result),
        });
        reader.readAsDataURL(blob);
      }),
      parent,
      parentRect,
      frame,
      captureFrame: {
        x: 0,
        y: 0,
        width: 1,
        height: 1,
      },
      mime: blob.type || mime,
      quality:
        (blob.type || mime) === "image/png" ? null : this.#round(quality),
      pixelRatio,
      pixelDimensions: {
        width: canvas.width,
        height: canvas.height,
      },
      background: resolvedBackground ?? "transparent",
      placementScale: 1,
      scrollIndependent: true,
      viewportIndependent: true,
    };
    this.#screenshotCache.set(element, {
      signature,
      capture,
    });
    return capture;
  };
  /**
   * Capture requested element PNGs into the current scene context.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {Promise<void>} Updates the capture context in place.
   */
  static #captureElementScreenshots = async context => {
    const htmlToImage = evidenceGlobal.htmlToImage;
    if (!htmlToImage?.toCanvas) {
      context.warnings.push({
        kind: "element-screenshots",
        message:
          "Element screenshots requested but htmlToImage.toCanvas is unavailable.",
      });
      return;
    }
    const previewCard = context.root.querySelector("#preview-card");
    if (!previewCard) {
      context.warnings.push({
        kind: "element-screenshots",
        message:
          "Element screenshots requested but #preview-card was not found.",
      });
      return;
    }
    const entries = [...context.elementsById]
      .filter(
        ([, element]) =>
          element === previewCard || previewCard.contains(element),
      )
      .filter(([, element]) => element.getBoundingClientRect().width > 0);
    const cardRect = previewCard.getBoundingClientRect();
    const mime = ["image/png", "image/webp", "image/jpeg"].includes(
      context.settings.elementScreenshotMime,
    )
      ? context.settings.elementScreenshotMime
      : "image/png";
    const quality = Math.max(
      0.1,
      Math.min(1, context.settings.elementScreenshotQuality ?? 0.92),
    );
    const skipAutoScale =
      context.settings.elementScreenshotSkipAutoScale ?? false;
    const background = context.settings.elementScreenshotBackground;
    /** Resolve the screenshot background color from settings.
     * @returns {string|null} Resolved background color or null for computed.
     */
    const resolvedBackground = (() => {
      const bg =
        background === "computed"
          ? null
          : ({
              white: "#fff",
              black: "#000",
            }[background] ?? null);
      return bg && !["transparent", "rgba(0, 0, 0, 0)"].includes(bg)
        ? bg
        : mime === "image/jpeg"
          ? "#fff"
          : null;
    })();
    const pixelRatio = Math.max(
      0.1,
      Math.min(
        context.settings.elementScreenshotPixelRatio ?? 1,
        (context.settings.elementScreenshotMaxDimension ?? Infinity) /
          Math.max(cardRect.width, cardRect.height),
      ),
    );
    const canvasW = Math.max(1, Math.round(cardRect.width * pixelRatio));
    const canvasH = Math.max(1, Math.round(cardRect.height * pixelRatio));
    let index = 0;
    /**
     * Derive capture next for the current rendered scene.
     * @returns {Promise<void>} Resolves when all entries are captured.
     */
    const captureNext = async () => {
      if (index >= entries.length) return;
      const entry = entries[index++];
      if (!entry) {
        await captureNext();
        return;
      }
      const [id, element] = entry;
      try {
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) {
          await captureNext();
          return;
        }
        const source = await htmlToImage.toCanvas(element, {
          pixelRatio,
          skipAutoScale,
          width: rect.width,
          height: rect.height,
          style: {
            overflow: "hidden",
          },
        });
        const canvas = Object.assign(document.createElement("canvas"), {
          width: canvasW,
          height: canvasH,
        });
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("2D canvas context is unavailable.");
        resolvedBackground &&
          Object.assign(ctx, {
            fillStyle: resolvedBackground,
          }) &&
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        const offsetX = Math.round((rect.left - cardRect.left) * pixelRatio);
        const offsetY = Math.round((rect.top - cardRect.top) * pixelRatio);
        ctx.drawImage(source, offsetX, offsetY);
        const blob = await new Promise(resolve => {
          canvas.toBlob(resolve, mime, quality);
        });
        if (!blob) throw new Error("Element screenshot could not be encoded.");
        const data = await new Promise((resolve, reject) => {
          const reader = Object.assign(new FileReader(), {
            onerror: reject,
            /**
             * Resolve the current FileReader operation after its terminal event.
             * @returns {void} Updates the capture context in place.
             */
            onloadend: () => resolve(reader.result),
          });
          reader.readAsDataURL(blob);
        });
        const assetId = `element-shot-${id}`;
        context.screenshotAssets.set(assetId, {
          id: assetId,
          elementRef: id,
          selector: this.#selectElement(element),
          mime: blob.type || mime,
          data,
          dimensions: {
            width: this.#round(cardRect.width),
            height: this.#round(cardRect.height),
          },
          pixelDimensions: {
            width: canvas.width,
            height: canvas.height,
          },
          pixelRatio: this.#round(pixelRatio),
          quality:
            (blob.type || mime) === "image/png" ? null : this.#round(quality),
          coordinateSystem: "target-element-direct",
          background: resolvedBackground ?? "transparent",
          targetVisibility: "direct-element-capture",
          scrollIndependent: true,
          viewportIndependent: true,
          source: "html-to-image",
        });
        const record = context.elementRegistry.get(id);
        if (record) record[String("screenshotRef")] = assetId;
      } catch (error) {
        const record = context.elementRegistry.get(id);
        if (record)
          record[String("screenshot")] = {
            unavailable: true,
            reason: error instanceof Error ? error.message : String(error),
          };
        context.warnings.push({
          sourceElementId: id,
          kind: "element-screenshots",
          message: `Element screenshot failed for ${this.#selectElement(element)}.`,
        });
      }
      await captureNext();
    };
    await Promise.all(
      Array.from(
        {
          length: Math.min(
            Math.max(
              1,
              Math.floor(context.settings.elementScreenshotConcurrency),
            ),
            entries.length,
          ),
        },
        captureNext,
      ),
    );
  };
  /**
   * Capture an element and write its image to the browser clipboard.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {SceneElementCaptureOptions} [options] Configuration for this operation; omitted fields use its declared defaults.
   * Side effects: Writes to the clipboard or initiates a download after capture.
   * Failure: Unsupported browser APIs or failed encoding reject the request.
   * @returns {Promise<{data:string,blob:Blob,frame:SceneRecord}>} Captured copyElementScreenshot evidence for the calling operation.
   */
  static copyElementScreenshot = async (element, options = {}) => {
    let capture = await this.#captureElementInParentFrame(element, {
      ...options,
      fresh: true,
    });
    if (
      !navigator.clipboard?.write ||
      typeof globalThis.ClipboardItem !== "function"
    )
      throw new Error(
        "Image clipboard writing is not supported in this browser.",
      );
    if (globalThis.ClipboardItem.supports?.(capture.blob.type) === false)
      capture = await this.#captureElementInParentFrame(element, {
        ...options,
        mime: "image/png",
        quality: 1,
        fresh: true,
      });
    await navigator.clipboard.write([
      new globalThis.ClipboardItem({
        [capture.blob.type]: capture.blob,
      }),
    ]);
    return capture;
  };
  /**
   * Capture an element and return its encoded image data URL.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {SceneElementCaptureOptions} [options] Configuration for this operation; omitted fields use its declared defaults.
   * @returns {Promise<string>} Captured captureElementDataUrl evidence for the calling operation.
   */
  static captureElementDataUrl = async (element, options = {}) => {
    const capture = await this.#captureElementInParentFrame(element, {
      ...options,
      fresh: true,
    });
    return capture.data;
  };
  /**
   * Derive source descriptor for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneRecord} Captured source description evidence for the calling operation.
   */
  static #sourceDescriptor = (element, context) => {
    const selector = this.#selectElement(element);
    return {
      elementRef: this.#elementId(element, context),
      tag: element.tagName.toLowerCase(),
      id: element.id || null,
      classes: [...element.classList],
      role: this.#serializedRole(element),
      name: this.#serializedName(element),
      ariaLabel: element.getAttribute("aria-label"),
      selector,
      rootSelector: this.#rootSelector(element, context.root),
      visualSelector: selector,
      html: this.#htmlSignature(element),
      interactive: this.#serializedInteractive(element),
      focusable: element instanceof HTMLElement && element.tabIndex >= 0,
    };
  };
  /**
   * Describe an element and its descendants without retaining live nodes.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneRecord} Captured serializeElement evidence for the calling operation.
   */
  static #serializeElement = (element, context) => {
    const selector = this.#selectElement(element);
    const role = this.#serializedRole(element);
    return {
      tag: element.tagName.toLowerCase(),
      selector,
      rootSelector: this.#rootSelector(element, context.root),
      outerHTML: element.outerHTML.replace(
        /(\s[\w:-]+=")data:[^"]*(")/gi,
        "$1<data-uri>$2",
      ),
      html: this.#htmlSignature(element),
      id: element.id || null,
      classes: [...element.classList],
      attributes: Object.fromEntries(
        [...element.attributes]
          .filter(
            ({ name }) =>
              !["id", "class"].includes(name) && !name.startsWith("data-"),
          )
          .map(({ name, value }) => [
            name,
            /^data:/i.test(value) ? `<${name}-data-uri>` : value,
          ]),
      ),
      dataset:
        element instanceof HTMLElement
          ? {
              ...element.dataset,
            }
          : {},
      properties: this.#ownElementProperties(element),
      text:
        element instanceof HTMLElement
          ? element.innerText.trim() || null
          : element.textContent?.trim() || null,
      role,
      name: this.#serializedName(element),
      value: "value" in element ? this.#jsonSafe(element.value) : null,
      interactive: this.#serializedInteractive(element),
      focusable: element instanceof HTMLElement && element.tabIndex >= 0,
      tabIndex: element instanceof HTMLElement ? element.tabIndex : -1,
      contentEditable:
        element instanceof HTMLElement && element.isContentEditable,
      state: this.#serializedState(element),
      form:
        "form" in element && element.form instanceof HTMLFormElement
          ? {
              id: element.form.id || null,
              selector: this.#selectElement(element.form),
              name:
                "name" in element ? String(element.name || "") || null : null,
              type:
                "type" in element ? String(element.type || "") || null : null,
              valid:
                "validity" in element &&
                typeof element.validity === "object" &&
                element.validity !== null &&
                "valid" in element.validity
                  ? element.validity.valid === true
                  : null,
            }
          : null,
      structure: {
        parent: element.parentElement
          ? this.#selectElement(element.parentElement)
          : null,
        children: [...element.children].map(child =>
          this.#selectElement(child),
        ),
        childCount: element.children.length,
        index: element.parentElement
          ? [...element.parentElement.children].indexOf(element)
          : null,
        shadowRoot: Boolean(element.shadowRoot),
      },
    };
  };
  /**
   * Cache a compact unique selector for the current document structure.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string} Captured selectElement evidence for the calling operation.
   */
  static #selectElement = element => {
    const cached = this.#selectorCache.get(element);
    if (cached) return cached;
    const parents = [element];
    while (parents.at(-1)?.parentElement) {
      const parent = parents.at(-1)?.parentElement;
      if (!parent) break;
      parents.push(parent);
    }
    let path = "";
    const selected = parents.reduce(
      /** @param {string|null} result @param {Element} current */
      (result, current) => {
        if (result) return result;
        const found = [
          current.id && `#${this.#cssEscape(current.id)}`,
          ...[...current.attributes]
            .filter(({ value }) => value)
            .flatMap(({ name, value }) => [
              `[${this.#cssEscape(name)}="${this.#cssEscape(value)}"]`,
              `${current.tagName.toLowerCase()}[${this.#cssEscape(name)}="${this.#cssEscape(value)}"]`,
            ]),
          ...[...current.classList].flatMap(name => [
            `.${this.#cssEscape(name)}`,
            `${current.tagName.toLowerCase()}.${this.#cssEscape(name)}`,
          ]),
          current.tagName.toLowerCase(),
        ]
          .filter(candidate => typeof candidate === "string")
          .sort((a, b) => a.length - b.length)
          .reduce(
            /** @param {{result:string|null,part:string|null}} selection @param {string} candidate */
            (selection, candidate) => {
              if (selection.result) return selection;
              let unique = false;
              let uniqueChild = false;
              try {
                unique =
                  document.querySelectorAll(
                    `${candidate}${path ? `>${path}` : ""}`,
                  ).length === 1;
                uniqueChild =
                  !current.parentElement ||
                  current.parentElement.querySelectorAll(`:scope>${candidate}`)
                    .length === 1;
              } catch {
                // Invalid selector candidates remain non-unique and are skipped.
              }
              return {
                result: unique ? `${candidate}${path ? `>${path}` : ""}` : null,
                part: selection.part || (uniqueChild ? candidate : null),
              };
            },
            /** @type {{result:string|null,part:string|null}} */ ({
              result: null,
              part: null,
            }),
          );
        if (found.result) return found.result;
        let part = found.part ?? current.tagName.toLowerCase();
        try {
          if (
            current.parentElement &&
            current.parentElement.querySelectorAll(`:scope>${part}`).length !==
              1
          )
            part += `:nth-child(${[...current.parentElement.children].indexOf(current) + 1})`;
        } catch {
          if (current.parentElement)
            part = `${current.tagName.toLowerCase()}:nth-child(${[...current.parentElement.children].indexOf(current) + 1})`;
        }
        path = path ? `${part}>${path}` : part;
        try {
          return document.querySelectorAll(path).length === 1 ? path : null;
        } catch {
          return null;
        }
      },
      /** @type {string|null} */ (null),
    );
    const result = selected ?? this.#uniqueSelector(element);
    this.#selectorCache.set(element, result);
    return result;
  };
  /**
   * Derive serialized role for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string|null} Captured serializedRole evidence for the calling operation.
   */
  static #serializedRole = element => {
    const html = element instanceof HTMLElement ? element : null;
    const input = element instanceof HTMLInputElement ? element : null;
    return (
      element.getAttribute("role") ||
      {
        A: element.hasAttribute("href") && "link",
        BUTTON: "button",
        TEXTAREA: "textbox",
        SELECT:
          element instanceof HTMLSelectElement && element.multiple
            ? "listbox"
            : "combobox",
        IMG: element instanceof HTMLImageElement && element.alt && "img",
        PROGRESS: "progressbar",
        METER: "meter",
        DETAILS: "group",
        SUMMARY: "button",
        NAV: "navigation",
        MAIN: "main",
        ASIDE: "complementary",
        HEADER: "banner",
        FOOTER: "contentinfo",
        FORM: "form",
      }[element.tagName] ||
      (element.tagName === "INPUT" &&
        input &&
        ({
          button: "button",
          submit: "button",
          reset: "button",
          checkbox: "checkbox",
          radio: "radio",
          range: "slider",
          number: "spinbutton",
          search: "searchbox",
        }[input.type] ||
          "textbox")) ||
      html?.getAttribute("role") ||
      null
    );
  };
  /**
   * Derive serialized name for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string|null} Captured serializedName evidence for the calling operation.
   */
  static #serializedName = element => {
    const html = element instanceof HTMLElement ? element : null;
    const labels =
      element instanceof HTMLInputElement ||
      element instanceof HTMLSelectElement ||
      element instanceof HTMLTextAreaElement
        ? element.labels
        : null;
    return (
      element.getAttribute("aria-label") ||
      element
        .getAttribute("aria-labelledby")
        ?.split(/\s+/)
        .map(id => document.getElementById(id)?.innerText.trim())
        .filter(Boolean)
        .join(" ") ||
      labels?.[0]?.innerText.trim() ||
      (element instanceof HTMLImageElement ? element.alt : null) ||
      html?.title ||
      html?.innerText.trim() ||
      null
    );
  };
  /**
   * Derive serialized interactive for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {boolean} Captured serializedInteractive evidence for the calling operation.
   */
  static #serializedInteractive = element => {
    const role = this.#serializedRole(element);
    const html = element instanceof HTMLElement ? element : null;
    return Boolean(
      role &&
        [
          "button",
          "link",
          "checkbox",
          "radio",
          "slider",
          "spinbutton",
          "textbox",
          "searchbox",
          "combobox",
          "listbox",
        ].includes(role) ||
      html?.onclick ||
      element.hasAttribute("tabindex") ||
      html?.isContentEditable,
    );
  };
  /**
   * Derive serialized state for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured serializedState evidence for the calling operation.
   */
  static #serializedState = element =>
    Object.fromEntries(
      [
        [
          "disabled",
          "disabled" in element
            ? element.disabled
            : element.getAttribute("aria-disabled"),
        ],
        [
          "checked",
          "checked" in element
            ? element.checked
            : element.getAttribute("aria-checked"),
        ],
        [
          "selected",
          "selected" in element
            ? element.selected
            : element.getAttribute("aria-selected"),
        ],
        ["expanded", element.getAttribute("aria-expanded")],
        ["pressed", element.getAttribute("aria-pressed")],
        [
          "required",
          "required" in element
            ? element.required
            : element.getAttribute("aria-required"),
        ],
        [
          "readOnly",
          "readOnly" in element
            ? element.readOnly
            : element.getAttribute("aria-readonly"),
        ],
        ["open", "open" in element ? element.open : null],
        [
          "hidden",
          element instanceof HTMLElement && element.hidden ||
            element.getAttribute("aria-hidden"),
        ],
        ["invalid", element.getAttribute("aria-invalid")],
        ["busy", element.getAttribute("aria-busy")],
        ["current", element.getAttribute("aria-current")],
      ].filter(([, value]) => value !== null && value !== undefined),
    );
  /**
   * Read serializable own properties without retaining DOM references.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {SceneRecord} Captured ownElementProperties evidence for the calling operation.
   */
  static #ownElementProperties = element => {
    const prototype = Object.getPrototypeOf(element);
    return Object.fromEntries(
      Reflect.ownKeys(element)
        .filter(key => !Reflect.has(prototype, key))
        .map(key => {
          try {
            return [String(key), this.#jsonSafe(Reflect.get(element, key))];
          } catch (error) {
            return [
              String(key),
              `[Unserializable:${error instanceof Error ? error.name : "Error"}]`,
            ];
          }
        }),
    );
  };
  /**
   * Project arbitrary browser property values into serializable evidence.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {SceneValue} Captured jsonSafe evidence for the calling operation.
   */
  static #jsonSafe = value => {
    const seen = new WeakSet();
    try {
      const serialized = JSON.stringify(value, (_, current) => {
        if (["bigint", "symbol"].includes(typeof current))
          return String(current);
        if (typeof current === "function")
          return `[Function${current.name ? `:${current.name}` : ""}]`;
        if (current instanceof Element) return current.outerHTML;
        if (current instanceof Node) return current.nodeName;
        if (
          current &&
          typeof current === "object" &&
          (seen.has(current) || !seen.add(current))
        )
          return "[Circular]";
        return current;
      });
      return serialized === undefined ? null : JSON.parse(serialized);
    } catch (error) {
      return `[Unserializable:${error instanceof Error ? error.name : "Error"}]`;
    }
  };
  /**
   * Derive css escape for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {string} Captured cssEscape evidence for the calling operation.
   */
  static #cssEscape = value => CSS.escape(String(value));
  /**
   * Derive selector segment for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string} Captured selectorSegment evidence for the calling operation.
   */
  static #selectorSegment = element => {
    const tag = element.tagName.toLowerCase();
    if (
      element.id &&
      document.querySelectorAll(`#${this.#cssEscape(element.id)}`).length === 1
    )
      return `#${this.#cssEscape(element.id)}`;
    for (const attribute of [
      "data-testid",
      "data-test",
      "name",
      "aria-label",
    ]) {
      const value = element.getAttribute(attribute);
      if (!value) continue;
      const candidate = `${tag}[${attribute}="${String(value)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')}"]`;
      try {
        if (document.querySelectorAll(candidate).length === 1) return candidate;
      } catch {
        // Invalid attribute selectors fall through to the class/position selector.
      }
    }
    const classes = [...element.classList]
      .filter(
        name =>
          name &&
          !/^is-|^has-|^active$|^selected$|^open$|^hover$|^focus$/.test(name),
      )
      .slice(0, 3)
      .map(name => `.${this.#cssEscape(name)}`)
      .join("");
    const base = `${tag}${classes}`;
    if (!element.parentElement) return base;
    const siblings = [...element.parentElement.children].filter(
      sibling => sibling.tagName === element.tagName,
    );
    return siblings.length > 1
      ? `${base}:nth-of-type(${siblings.indexOf(element) + 1})`
      : base;
  };
  /**
   * Derive unique selector for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string} Captured uniqueSelector evidence for the calling operation.
   */
  static #uniqueSelector = element => {
    if (element.id) {
      const idSelector = `#${this.#cssEscape(element.id)}`;
      try {
        if (document.querySelectorAll(idSelector).length === 1)
          return idSelector;
      } catch {
        // An invalid ID selector falls through to the ancestor path.
      }
    }
    const segments = [];
    for (
      let current = /** @type {Element|null} */ (element);
      current instanceof Element;
      current = current.parentElement
    ) {
      const segment = this.#selectorSegment(current);
      segments.unshift(segment);
      const candidate = segments.join(" > ");
      try {
        if (document.querySelectorAll(candidate).length === 1) return candidate;
      } catch {
        // Invalid ancestor selectors fall through to the next path segment.
      }
      if (segment.startsWith("#")) return candidate;
    }
    return segments.join(" > ");
  };
  /**
   * Derive root selector for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {Element} root Root element defining the capture or lookup boundary.
   * @returns {string} Captured rootSelector evidence for the calling operation.
   */
  static #rootSelector = (element, root) => {
    if (element === root) return ":scope";
    const segments = [];
    for (
      let current = /** @type {Element|null} */ (element);
      current instanceof Element && current !== root;
      current = current.parentElement
    )
      segments.unshift(this.#selectorSegment(current));
    return `:scope > ${segments.join(" > ")}`;
  };
  /**
   * Derive html signature for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @returns {string} Captured htmlSignature evidence for the calling operation.
   */
  static #htmlSignature = element => {
    /**
     * Derive compact value for the current rendered scene.
     * @param {string} name Name used by this operation.
     * @param {string} value Value read from the current DOM, configuration or serialized scene.
     * @returns {string} Compact CSS value string.
     */
    const compactValue = (name, value) => {
      if (/^data:/i.test(value)) return `<${name}-data-uri>`;
      const compact = value.replace(/\s+/g, " ").trim();
      return compact.length > 120 ? `${compact.slice(0, 117)}...` : compact;
    };
    const attributes = [...element.attributes]
      .filter(({ name }) => !["style", "srcset"].includes(name))
      .map(({ name, value }) => {
        const compact = compactValue(name, value);
        const escaped = compact
          .replace(/&/g, "&amp;")
          .replace(/"/g, "&quot;")
          .replace(/</g, "&lt;");
        return value ? `${name}="${escaped}"` : name;
      })
      .join(" ");
    return `<${element.tagName.toLowerCase()}${attributes ? ` ${attributes}` : ""}>`;
  };
  /**
   * Derive element id for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {string} Captured elementId evidence for the calling operation.
   */
  static #elementId = (element, context) => {
    let id = context.elementIds.get(element);
    if (!id) {
      id = `el-${context.nextId++}`;
      context.elementIds.set(element, id);
    }
    return id;
  };
  /**
   * Derive element from id for the current rendered scene.
   * @param {string} id Id used by this operation.
   * @param {Element} root Root element defining the capture or lookup boundary.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {Element|null} Captured elementFromId evidence for the calling operation.
   */
  static #elementFromId = (id, root, context) => {
    if (context.elementIds.get(root) === id) return root;
    for (const element of root.querySelectorAll("*")) {
      if (context.elementIds.get(element) === id) return element;
    }
    return null;
  };
  /**
   * Derive grid regions for the current rendered scene.
   * @param {SceneRecord[][]} grid Grid used by this operation.
   * @param {?SceneRgba} backdrop Backdrop used by this operation.
   * @returns {SceneRecord[]} Captured gridRegions evidence for the calling operation.
   */
  static #gridRegions = (grid, backdrop) => {
    const typedGrid =
      /** @type {{row:number,column:number,color:SceneColorDescriptor}[][]} */ (
        /** @type {unknown} */ (grid)
      );
    const rows = typedGrid.length;
    const columns = typedGrid[0]?.length ?? 0;
    if (!rows || !columns) return [];
    const visited = Array.from(
      {
        length: rows,
      },
      () => Array(columns).fill(false),
    );
    /** @type {[number, number][]} */
    const directions = [
      [-1, 0],
      [0, 1],
      [1, 0],
      [0, -1],
    ];
    /**
     * Derive similar for the current rendered scene.
     * @param {{row:number,column:number,color:SceneColorDescriptor}} first First used by this operation.
     * @param {{row:number,column:number,color:SceneColorDescriptor}} second Second used by this operation.
     * @returns {boolean} Whether the two values are similar.
     */
    const similar = (first, second) => {
      const firstColor = first.color.rgba;
      const secondColor = second.color.rgba;
      return (
        (this.#perceivedContrast(first.color, second.color, backdrop) ??
          Infinity) <= 1.35 &&
        Math.sqrt(
          ((firstColor[0] - secondColor[0]) / 255) ** 2 +
            ((firstColor[1] - secondColor[1]) / 255) ** 2 +
            ((firstColor[2] - secondColor[2]) / 255) ** 2,
        ) /
          Math.sqrt(3) <=
          0.22
      );
    };
    /** @type {SceneRecord[]} */
    const regions = [];
    for (let row = 0; row < rows; row++) {
      for (let column = 0; column < columns; column++) {
        if (visited[row]?.[column]) continue;
        /** @type {[number, number][]} */
        const queue = [[row, column]];
        /** @type {{row:number,column:number,color:SceneColorDescriptor}[]} */
        const cells = [];
        const seed = typedGrid[row]?.[column];
        if (!seed) continue;
        const visitedRow = visited[row];
        if (!visitedRow) continue;
        visitedRow[column] = true;
        while (queue.length) {
          const current = queue.shift();
          if (!current) break;
          const [currentRow, currentColumn] = current;
          const cell = typedGrid[currentRow]?.[currentColumn];
          if (!cell) continue;
          cells.push(cell);
          for (const [rowOffset, columnOffset] of directions) {
            const targetRow = currentRow + rowOffset;
            const targetColumn = currentColumn + columnOffset;
            const target = typedGrid[targetRow]?.[targetColumn];
            if (
              !target ||
              visited[targetRow]?.[targetColumn] ||
              !similar(cell, target) ||
              !similar(seed, target)
            )
              continue;
            if (!visited[targetRow]) continue;
            visited[targetRow][targetColumn] = true;
            queue.push([targetRow, targetColumn]);
          }
        }
        const membership = new Set(
          cells.map(
            ({ row: cellRow, column: cellColumn }) =>
              `${cellRow}:${cellColumn}`,
          ),
        );
        /** @type {number[]} */
        const boundaryRatios = [];
        let exposedEdges = 0;
        for (const cell of cells)
          for (const [rowOffset, columnOffset] of directions) {
            const target =
              typedGrid[cell.row + rowOffset]?.[cell.column + columnOffset];
            if (!target) {
              exposedEdges++;
              continue;
            }
            if (membership.has(`${target.row}:${target.column}`)) continue;
            exposedEdges++;
            boundaryRatios.push(
              this.#perceivedContrast(cell.color, target.color, backdrop) ?? 1,
            );
          }

        const colors = cells.map(({ color }) => color.rgba);
        const averageColor = colors.length
          ? this.#colorDescriptor([
              colors.reduce((sum, color) => sum + color[0], 0) / colors.length,
              colors.reduce((sum, color) => sum + color[1], 0) / colors.length,
              colors.reduce((sum, color) => sum + color[2], 0) / colors.length,
              colors.reduce((sum, color) => sum + color[3], 0) / colors.length,
            ])
          : null;
        const minRow = Math.min(...cells.map(({ row: cellRow }) => cellRow));
        const maxRow = Math.max(...cells.map(({ row: cellRow }) => cellRow));
        const minColumn = Math.min(
          ...cells.map(({ column: cellColumn }) => cellColumn),
        );
        const maxColumn = Math.max(
          ...cells.map(({ column: cellColumn }) => cellColumn),
        );
        const area = cells.length / (rows * columns);
        const averageBoundary = boundaryRatios.length
          ? boundaryRatios.reduce((sum, ratio) => sum + ratio, 0) /
            boundaryRatios.length
          : 1;
        regions.push({
          id: `region-${regions.length + 1}`,
          cells: cells.map(({ row: cellRow, column: cellColumn }) => [
            cellRow,
            cellColumn,
          ]),
          cellCount: cells.length,
          area: this.#round(area),
          boundingBox: {
            x: this.#round(minColumn / columns),
            y: this.#round(minRow / rows),
            width: this.#round((maxColumn - minColumn + 1) / columns),
            height: this.#round((maxRow - minRow + 1) / rows),
          },
          averageColor,
          contrastToSurroundings: boundaryRatios.length
            ? {
                min: this.#round(Math.min(...boundaryRatios)),
                max: this.#round(Math.max(...boundaryRatios)),
                average: this.#round(averageBoundary),
              }
            : null,
          boundary: {
            exposedEdgeCount: exposedEdges,
            exposedFractionOfPossible: this.#round(
              exposedEdges / Math.max(1, cells.length * 4),
            ),
          },
          wcag22GraphicalObjectIfMeaningful: {
            criterion: "1.4.11 Non-text Contrast",
            required: 3,
            applicability:
              "conditional-on-region-being-required-for-understanding",
            passesIfApplicable: boundaryRatios.length
              ? Math.min(...boundaryRatios) >= 3
              : null,
          },
          perception: this.#salienceMetrics(
            averageBoundary,
            area,
            Math.min(
              (maxColumn - minColumn + 1) / columns,
              (maxRow - minRow + 1) / rows,
            ),
            1,
            exposedEdges / Math.max(1, cells.length * 4),
          ),
        });
      }
    }
    return regions.sort(
      (first, second) =>
        Number(second[String("area")]) - Number(first[String("area")]) ||
        Number(
          /** @type {SceneRecord} */ (second[String("perception")])[
            String("score")
          ],
        ) -
          Number(
            /** @type {SceneRecord} */ (first[String("perception")])[
              String("score")
            ],
          ),
    );
  };
  /**
   * Derive resolve visual contrast for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {void} Updates the capture context in place.
   */
  static #resolveVisualContrast = context => {
    for (const object of context.objects) {
      if (object.type === "text" || object.type === "control" || !object.frame)
        continue;
      const source = this.#elementFromId(
        object.sourceElementId,
        context.root,
        context,
      );
      const colors = this.#visualObjectColors(object, context);
      if (!source || !colors.length) continue;
      const rawRect = this.#rectFromFrame(
        object.visibleFrame ?? object.frame,
        context.rootRect,
      );
      const rect = {
        left: rawRect.left - (rawRect.width <= 0 ? 0.5 : 0),
        top: rawRect.top - (rawRect.height <= 0 ? 0.5 : 0),
        right: rawRect.right + (rawRect.width <= 0 ? 0.5 : 0),
        bottom: rawRect.bottom + (rawRect.height <= 0 ? 0.5 : 0),
        width: Math.max(1, rawRect.width),
        height: Math.max(1, rawRect.height),
      };
      const normalizedPoints = /** @type {[number, number][]} */ ([
        [0.5, 0.5],
        [0.15, 0.15],
        [0.85, 0.15],
        [0.15, 0.85],
        [0.85, 0.85],
      ]);
      const points = normalizedPoints.map(
        ([x, y]) =>
          /** @type {[number, number]} */ ([
            rect.left + rect.width * x,
            rect.top + rect.height * y,
          ]),
      );
      const backgrounds =
        /** @type {{color:SceneRgba,source:string,confidence:string}[]} */ (
          /** @type {unknown} */ (
            points
              .map(([x, y]) => this.#backgroundSampleAt(source, x, y, context))
              .filter(Boolean)
          )
        );
      if (!backgrounds.length) continue;
      const ratios = colors.flatMap(foreground =>
        backgrounds.map(background => ({
          ratio: this.#contrastRatio(
            foreground[3] < 1
              ? this.#alphaComposite(foreground, background.color)
              : foreground,
            background.color,
          ),
          foreground: this.#colorDescriptor(foreground),
          background: this.#colorDescriptor(background.color),
          source: background.source,
          confidence: background.confidence,
        })),
      );
      const values = ratios.map(({ ratio }) => ratio);
      const minimum = Math.min(...values);
      const wcagConditional = [
        "line",
        "contour",
        "icon",
        "svg",
        "svg-render",
        "image",
        "canvas",
        "video",
      ].includes(object.type);
      object[String("contrast")] = {
        status: "resolved",
        local: {
          min: this.#round(minimum),
          max: this.#round(Math.max(...values)),
          average: this.#round(
            values.reduce((sum, value) => sum + value, 0) / values.length,
          ),
          samples: ratios.map(entry => ({
            ...entry,
            ratio: this.#round(entry.ratio),
          })),
        },
        wcag22: wcagConditional
          ? {
              criterion: "1.4.11 Non-text Contrast",
              required: 3,
              applicability:
                "conditional-on-visual-information-being-required-to-identify-state-or-understand-content",
              passesIfApplicable: minimum >= 3,
              thresholdComparison: "unrounded-ratio",
            }
          : {
              criterion: null,
              applicability:
                "surface-separation-is-descriptive-not-automatically-normative",
            },
      };
    }
  };
  /**
   * Derive visual object colors for the current rendered scene.
   * @param {SceneObject} object Object used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneRgba[]} Captured visualObjectColors evidence for the calling operation.
   */
  static #visualObjectColors = (object, context) => {
    const descriptors =
      object.type === "line"
        ? [object[String("color")]]
        : object.type === "contour"
          ? [
              object[String("color")],
              ...Object.values(object[String("sides")] ?? {}).map(
                ({ color }) => color,
              ),
            ]
          : object.type === "surface"
            ? [object[String("appearance")]?.background?.color]
            : ["image", "canvas", "video", "svg-render"].includes(object.type)
              ? [object[String("raster")]?.averageColor]
              : object.type === "icon"
                ? [
                    context.iconAssets.get(object[String("assetRef")])?.[
                      String("averageColor")
                    ],
                  ]
                : [];
    return /** @type {SceneRgba[]} */ (
      /** @type {unknown} */ (
        descriptors
          .filter(Boolean)
          .map(({ rgba }) => rgba)
          .filter(rgba => rgba?.length === 4 && rgba[3] > 0)
      )
    );
  };
  /**
   * Derive resolve control contrast for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {void} Updates the capture context in place.
   */
  static #resolveControlContrast = context => {
    const bySource = context.objects.reduce((groups, object) => {
      const values = groups.get(object.sourceElementId) ?? [];
      values.push(object);
      groups.set(object.sourceElementId, values);
      return groups;
    }, /** @type {Map<string, SceneObject[]>} */ (new Map()));
    for (const control of context.objects.filter(
      ({ type }) => type === "control",
    )) {
      /**
       * Read an object's resolved local minimum contrast ratio.
       * @param {SceneObject} object Object used by this operation.
       * @returns {number|undefined} Local minimum contrast when present.
       */
      const contrastMin = object =>
        /** @type {number|undefined} */ (
          /** @type {SceneRecord|undefined} */
          (
            /** @type {SceneRecord|undefined} */
            (object[String("contrast")])?.[String("local")]
          )?.[String("min")]
        );
      const candidates = (bySource.get(control.sourceElementId) ?? [])
        .filter(object => object !== control && contrastMin(object) != null)
        .map(object => ({
          objectId: object.id,
          type: object.type,
          ratio: /** @type {number} */ (contrastMin(object)),
        }));
      if (!candidates.length) continue;
      const minimum = Math.min(...candidates.map(({ ratio }) => ratio));
      control[String("contrast")] = {
        status: "resolved-from-visual-indicators",
        indicatorCandidates: candidates,
        minIndicatorContrast: this.#round(minimum),
        wcag22: {
          criterion: "1.4.11 Non-text Contrast",
          required: 3,
          applicability:
            "conditional-on-these-indicators-being-required-to-identify-the-control-or-state",
          passesIfApplicable: minimum >= 3,
          thresholdComparison: "unrounded-ratio-when-source-sample-available",
        },
      };
    }
  };
  /**
   * Derive resolve perception for the current rendered scene.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {void} Updates the capture context in place.
   */
  static #resolvePerception = context => {
    for (const object of context.objects) {
      if (!object.frame) continue;
      const frame = object.visibleFrame ?? object.frame;
      const source = this.#elementFromId(
        object.sourceElementId,
        context.root,
        context,
      );
      const thickness = source
        ? this.#normalizedVisualThickness(object, source, context.rootRect)
        : null;
      const contrastRecord = /** @type {SceneRecord|undefined} */ (
        object[String("contrast")]
      );
      const localContrast = /** @type {SceneRecord|undefined} */ (
        contrastRecord?.[String("local")]
      );
      const rasterContrast = /** @type {SceneRecord|undefined} */ (
        /** @type {SceneRecord|undefined} */
        (object[String("raster")])?.[String("averageContrast")]
      );
      const contrast =
        object.type === "text"
          ? /** @type {number|undefined} */ (contrastRecord?.[String("min")])
          : object.type === "control"
            ? /** @type {number|undefined} */ (
                contrastRecord?.[String("minIndicatorContrast")]
              )
            : /** @type {number|undefined} */ (
                localContrast?.[String("min")] ??
                  /** @type {number|undefined} */ (
                    rasterContrast?.[String("toBackdrop")]
                  ) ??
                  1
              );
      const area = Math.max(0, frame.width) * Math.max(0, frame.height);
      const effectiveArea =
        object.type === "line"
          ? (object[String("orientation")] === "horizontal"
              ? Math.max(0, frame.width)
              : Math.max(0, frame.height)) * Math.max(thickness ?? 0, 1e-6)
          : object.type === "contour"
            ? Math.max(thickness ?? 0, 1e-6) *
              2 *
              (Math.max(0, frame.width) + Math.max(0, frame.height))
            : area;
      const minimumDimension =
        ["line", "contour"].includes(object.type) && thickness != null
          ? thickness
          : Math.min(Math.max(0, frame.width), Math.max(0, frame.height));
      object[String("perception")] = {
        size: {
          width: this.#round(Math.max(0, frame.width)),
          height: this.#round(Math.max(0, frame.height)),
          area: this.#round(area),
          effectivePaintArea: this.#round(effectiveArea),
          minimumDimension: this.#round(minimumDimension),
          thickness: thickness == null ? null : this.#round(thickness),
        },
        visibilityFraction: object.visibility?.visibleArea ?? 1,
        salience: this.#salienceMetrics(
          contrast ?? 1,
          effectiveArea,
          Math.max(
            thickness ??
              Math.min(Math.max(0, frame.width), Math.max(0, frame.height)),
            1e-6,
          ),
          thickness == null ? 1 : this.#clamp(thickness * 120, 0, 1),
          object.visibility?.visibleArea ?? 1,
        ),
        normativeStatus: "non-normative-perceptual-model",
        note: "WCAG contrast thresholds remain separate; this score estimates noticeability from contrast, normalized size, thickness and visible exposure.",
      };
    }
  };
  /**
   * Derive salience metrics for the current rendered scene.
   * @param {number} contrastRatio Contrastratio used by this operation.
   * @param {number} area Area used by this operation.
   * @param {number} minimumDimension Minimumdimension used by this operation.
   * @param {number} [thicknessFactor] Thicknessfactor used by this operation.
   * @param {number} [exposure] Exposure used by this operation.
   * @returns {SceneRecord} Captured salienceMetrics evidence for the calling operation.
   */
  static #salienceMetrics = (
    contrastRatio,
    area,
    minimumDimension,
    thicknessFactor = 1,
    exposure = 1,
  ) => {
    const contrast = Number.isFinite(contrastRatio)
      ? this.#clamp(contrastRatio, 1, 21)
      : 1;
    const contrastStrength = Math.log2(contrast) / Math.log2(21);
    const sizeStrength = 1 - Math.exp(-8 * Math.sqrt(Math.max(0, area)));
    const dimensionStrength = 1 - Math.exp(-18 * Math.max(0, minimumDimension));
    const geometryStrength = this.#clamp(
      (sizeStrength * 0.7 + dimensionStrength * 0.3) * thicknessFactor,
      0,
      1,
    );
    const score = this.#clamp(
      contrastStrength *
        (0.3 + geometryStrength * 0.7) *
        this.#clamp(exposure, 0, 1),
      0,
      1,
    );
    return {
      score: this.#round(score),
      classification:
        score >= 0.72
          ? "dominant"
          : score >= 0.48
            ? "strong"
            : score >= 0.25
              ? "moderate"
              : "low",
      components: {
        contrast: this.#round(contrastStrength),
        size: this.#round(sizeStrength),
        minimumDimension: this.#round(dimensionStrength),
        thickness: this.#round(thicknessFactor),
        exposure: this.#round(this.#clamp(exposure, 0, 1)),
      },
      inputContrastRatio: this.#round(contrast),
      model: "log-contrast × saturating-size × thickness × exposure",
      wcag: false,
    };
  };
  /**
   * Derive normalized visual thickness for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {SceneObject} object Object used by this operation.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} rootRect Rootrect used by this operation.
   * @returns {number|null} Captured normalizedVisualThickness evidence for the calling operation.
   */
  static #normalizedVisualThickness = (object, element, rootRect) => {
    const style = getComputedStyle(element);
    if (object.type === "line") {
      const side = object[String("sourceKind")]?.replace("border-", "");
      const suffix = side ? `${side[0].toUpperCase()}${side.slice(1)}` : null;
      const width = suffix
        ? parseFloat(
            style.getPropertyValue(`border-${suffix.toLowerCase()}-width`),
          ) || 0
        : 0;
      return this.#ratio(
        width,
        object[String("orientation")] === "horizontal"
          ? rootRect.height
          : rootRect.width,
      );
    }
    if (object.type === "contour") {
      const widths = ["Top", "Right", "Bottom", "Left"].map(
        suffix =>
          parseFloat(
            style.getPropertyValue(`border-${suffix.toLowerCase()}-width`),
          ) || 0,
      );
      const outline = parseFloat(style.outlineWidth) || 0;
      return this.#ratio(
        Math.max(outline, ...widths),
        Math.min(rootRect.width, rootRect.height),
      );
    }
    return null;
  };
  /**
   * Attach inferred row, column and placement descriptions to scene containers.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * Side effects: Updates capture-owned records; does not persist CMS content.
   * @returns {SceneRecord[]} Captured inferSpatialLayouts evidence for the calling operation.
   */
  static #inferSpatialLayouts = context => {
    const containers = [
      context.root,
      ...context.root.querySelectorAll("*"),
    ].filter(
      element =>
        !(element instanceof SVGElement) &&
        this.#isRendered(element, context.settings.opacityThreshold),
    );
    return containers
      .flatMap(container => {
        const children = [...container.children].filter(
          child =>
            !(child instanceof SVGElement) &&
            this.#isRendered(child, context.settings.opacityThreshold),
        );
        if (!children.length) return [];
        const containerRect = container.getBoundingClientRect();
        const rootArea = Math.max(
          1e-9,
          context.rootRect.width * context.rootRect.height,
        );
        const containerAreaFraction =
          containerRect.width * containerRect.height / rootArea;
        if (
          children.length === 1 &&
          container !== context.root &&
          containerAreaFraction < 0.012
        )
          return [];
        const layout = this.#inferContainerLayout(container, children, context);
        if (!layout) return [];
        const meaningfulPattern = !["free", "single"].includes(
          layout[String("inference")].pattern,
        );
        const meaningfulSingle =
          layout[String("inference")].pattern === "single" &&
          containerAreaFraction >= 0.08 &&
          (layout[String("items")][0]?.frame.width < 0.78 ||
            layout[String("items")][0]?.frame.height < 0.78);
        return container === context.root ||
          meaningfulPattern ||
          meaningfulSingle
          ? [layout]
          : [];
      })
      .sort(
        (first, second) =>
          second[String("scope")].frame.width *
            second[String("scope")].frame.height -
          first[String("scope")].frame.width *
            first[String("scope")].frame.height,
      );
  };
  /**
   * Derive infer container layout for the current rendered scene.
   * @param {Element} container Container used by this operation.
   * @param {Element[]} children Children used by this operation.
   * @param {DescribeContext} context Capture-owned object registry, geometry and sampled visual evidence.
   * @returns {SceneRecord|null} Captured inferContainerLayout evidence for the calling operation.
   */
  static #inferContainerLayout = (container, children, context) => {
    const containerRect = container.getBoundingClientRect();
    if (containerRect.width <= 0 || containerRect.height <= 0) return null;
    /** @type {SceneLayoutItem[]} */
    const items = children
      .map(child => ({
        element: child,
        sourceElementId: this.#elementId(child, context),
        source: this.#sourceDescriptor(child, context),
        frame: this.#spatialFrame(child, container),
      }))
      .filter(({ frame }) => frame.width > 0 && frame.height > 0);
    if (!items.length) return null;
    const columns = this.#inferAxisTracks(
      items,
      "x",
      context.settings.spatialMaxTracks,
      context.settings.spatialTolerance,
    );
    const rows = this.#inferAxisTracks(
      items,
      "y",
      context.settings.spatialMaxTracks,
      context.settings.spatialTolerance,
    );
    const placements = items.map(item =>
      this.#spatialPlacement(item, columns, rows),
    );
    const cells = this.#spatialCells(placements, columns, rows);
    const overlapPairs = items.flatMap((first, firstIndex) =>
      items
        .slice(firstIndex + 1)
        .map(second =>
          this.#frameIntersection(first.frame, second.frame) ? 1 : 0,
        ),
    );
    const overlapFraction = overlapPairs.length
      ? overlapPairs.reduce(
          (sum, value) => sum + value,
          /** @type {number} */ (0),
        ) / overlapPairs.length
      : 0;
    const occupiedCells = cells.filter(
      ({ occupancy }) => occupancy !== "empty",
    );
    const enrichedPlacements = placements.map(placement => {
      const coveredCells = cells.filter(
        ({ row, column }) =>
          row >= placement.placement.rowStart &&
          row <= placement.placement.rowEnd &&
          column >= placement.placement.columnStart &&
          column <= placement.placement.columnEnd,
      );
      const aloneInEveryCoveredCell = coveredCells.every(
        ({ occupants }) => occupants.length === 1,
      );
      const sharedCellCount = coveredCells.filter(
        ({ occupants }) => occupants.length > 1,
      ).length;
      const spannedArea = coveredCells.reduce(
        (sum, { frame }) => sum + frame.width * frame.height,
        0,
      );
      return {
        ...placement,
        placement: {
          ...placement.placement,
          occupancy: {
            coveredCellCount: coveredCells.length,
            aloneInEveryCoveredCell,
            sharedCellCount,
            role: aloneInEveryCoveredCell
              ? placement.placement.columnSpan > 1 ||
                placement.placement.rowSpan > 1
                ? "alone-spanning-cells"
                : "alone-in-cell"
              : "shares-cell",
            fillOfCoveredCells: this.#round(
              placement.frame.width * placement.frame.height /
                Math.max(1e-9, spannedArea),
            ),
          },
        },
      };
    });
    const pattern =
      overlapFraction > 0.35
        ? "layered"
        : columns.length > 1 && rows.length > 1
          ? "grid"
          : columns.length > 1
            ? "columns"
            : rows.length > 1
              ? "rows"
              : items.length === 1
                ? "single"
                : "free";
    const alignmentEvidence = this.#spatialAlignmentEvidence(
      placements,
      columns,
      rows,
    );
    const occupancyCoherence = occupiedCells.length
      ? occupiedCells.filter(({ occupants }) => occupants.length <= 1).length /
        occupiedCells.length
      : 0;
    const confidence = this.#clamp(
      0.3 +
        (columns.length > 1 || rows.length > 1 ? 0.22 : 0) +
        alignmentEvidence * 0.28 +
        occupancyCoherence * 0.2 -
        overlapFraction * 0.18,
      0,
      1,
    );
    const style = getComputedStyle(container);
    return {
      id: `layout-${this.#elementId(container, context)}`,
      scope: {
        sourceElementId: this.#elementId(container, context),
        source: this.#sourceDescriptor(container, context),
        frame: this.#frame(containerRect, context.rootRect),
        coordinateSpace:
          this.#scrollState(container).x.scrollable ||
          this.#scrollState(container).y.scrollable
            ? "scroll-content"
            : "container-box",
      },
      inference: {
        basis: "rendered-geometry-only",
        pattern,
        confidence: this.#round(confidence),
        declaredDisplayForReferenceOnly: style.display,
        declaredGridOrFlexNotUsedForInference: true,
        overlapFraction: this.#round(overlapFraction),
      },
      columns: columns.map((track, index) => ({
        index,
        ...track,
        label: this.#axisTrackLabel(index, columns.length, "x"),
      })),
      rows: rows.map((track, index) => ({
        index,
        ...track,
        label: this.#axisTrackLabel(index, rows.length, "y"),
      })),
      density: {
        itemCount: items.length,
        cellCount: cells.length,
        occupiedCells: occupiedCells.length,
        occupiedCellFraction: this.#ratio(
          occupiedCells.length,
          Math.max(1, cells.length),
        ),
        averageObjectsPerOccupiedCell: occupiedCells.length
          ? this.#round(
              occupiedCells.reduce(
                (sum, { occupants }) => sum + occupants.length,
                0,
              ) / occupiedCells.length,
            )
          : 0,
        alignmentEvidence: this.#round(alignmentEvidence),
      },
      cells,
      items: enrichedPlacements.map(({ element, ...placement }) => placement),
    };
  };
  /**
   * Derive spatial frame for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {Element} container Container used by this operation.
   * @returns {SceneFrame} Captured spatialFrame evidence for the calling operation.
   */
  static #spatialFrame = (element, container) => {
    const rect = element.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const scrollX =
      container.scrollWidth > container.clientWidth + 0.5
        ? container.scrollLeft
        : 0;
    const scrollY =
      container.scrollHeight > container.clientHeight + 0.5
        ? container.scrollTop
        : 0;
    const widthBase = Math.max(1, container.scrollWidth || containerRect.width);
    const heightBase = Math.max(
      1,
      container.scrollHeight || containerRect.height,
    );
    return {
      x: this.#round((rect.left - containerRect.left + scrollX) / widthBase),
      y: this.#round((rect.top - containerRect.top + scrollY) / heightBase),
      width: this.#round(rect.width / widthBase),
      height: this.#round(rect.height / heightBase),
    };
  };
  /**
   * Derive infer axis tracks for the current rendered scene.
   * @param {SceneLayoutItem[]} items Items used by this operation.
   * @param {string} axis Axis used by this operation.
   * @param {number} maxTracks Maxtracks used by this operation.
   * @param {number} tolerance Tolerance used by this operation.
   * @returns {SceneTrack[]} Captured inferAxisTracks evidence for the calling operation.
   */
  static #inferAxisTracks = (items, axis, maxTracks, tolerance) => {
    const startKey = axis === "x" ? "x" : "y";
    const sizeKey = axis === "x" ? "width" : "height";
    const sizes = items
      .map(({ frame }) => frame[sizeKey])
      .filter(value => value > 0)
      .sort((a, b) => a - b);
    const median = sizes[Math.floor(sizes.length / 2)] ?? 1;
    const anchors = items.filter(
      ({ frame }) =>
        frame[sizeKey] < 0.82 &&
        frame[sizeKey] <= Math.max(median * 1.65, 0.18),
    );
    const candidates = (anchors.length >= 2 ? anchors : items)
      .map(item => ({
        item,
        center: item.frame[startKey] + item.frame[sizeKey] / 2,
        size: item.frame[sizeKey],
      }))
      .sort((first, second) => first.center - second.center);
    const threshold = Math.max(tolerance, Math.min(0.16, median * 0.32));
    /** @type {{center:number,values:{item:SceneLayoutItem,center:number,size:number}[]}[]} */
    const clusters = [];
    for (const candidate of candidates) {
      const cluster = clusters.find(
        ({ center }) => Math.abs(center - candidate.center) <= threshold,
      );
      if (cluster) {
        cluster.values.push(candidate);
        cluster.center =
          cluster.values.reduce((sum, value) => sum + value.center, 0) /
          cluster.values.length;
      } else
        clusters.push({
          center: candidate.center,
          values: [candidate],
        });
    }
    while (clusters.length > maxTracks) {
      let mergeIndex = 0;
      let minimumGap = Infinity;
      for (let index = 0; index < clusters.length - 1; index++) {
        const left = clusters[index];
        const right = clusters[index + 1];
        if (!left || !right) continue;
        const gap = right.center - left.center;
        if (gap < minimumGap) {
          minimumGap = gap;
          mergeIndex = index;
        }
      }
      const firstCluster = clusters[mergeIndex];
      const secondCluster = clusters[mergeIndex + 1];
      if (!firstCluster || !secondCluster) break;
      const mergedValues = [...firstCluster.values, ...secondCluster.values];
      clusters.splice(mergeIndex, 2, {
        values: mergedValues,
        center:
          mergedValues.reduce((sum, value) => sum + value.center, 0) /
          mergedValues.length,
      });
    }
    clusters.sort((first, second) => first.center - second.center);
    if (!clusters.length)
      return [
        {
          start: 0,
          end: 1,
          size: 1,
          center: 0.5,
        },
      ];
    if (clusters.length === 1)
      return [
        {
          start: 0,
          end: 1,
          size: 1,
          center: 0.5,
        },
      ];
    const boundaries = [
      0,
      ...clusters
        .slice(0, -1)
        .map((cluster, index) =>
          this.#clamp(
            (cluster.center + (clusters[index + 1]?.center ?? cluster.center)) /
              2,
            0,
            1,
          ),
        ),
      1,
    ];
    return clusters.map((cluster, index) => ({
      start: this.#round(boundaries[index] ?? 0),
      end: this.#round(boundaries[index + 1] ?? 1),
      size: this.#round(
        (boundaries[index + 1] ?? 1) - (boundaries[index] ?? 0),
      ),
      center: this.#round(cluster.center),
    }));
  };
  /**
   * Derive spatial placement for the current rendered scene.
   * @param {SceneLayoutItem} item Header item or scene placement record owned by the caller.
   * @param {SceneTrack[]} columns Columns used by this operation.
   * @param {SceneTrack[]} rows Rows used by this operation.
   * @returns {ScenePlacement} Captured spatialPlacement evidence for the calling operation.
   */
  static #spatialPlacement = (item, columns, rows) => {
    const columnIndexes = this.#tracksCovered(
      item.frame.x,
      item.frame.width,
      columns,
    );
    const rowIndexes = this.#tracksCovered(
      item.frame.y,
      item.frame.height,
      rows,
    );
    const columnStart = Math.min(...columnIndexes);
    const columnEnd = Math.max(...columnIndexes);
    const rowStart = Math.min(...rowIndexes);
    const rowEnd = Math.max(...rowIndexes);
    const horizontal =
      columns.length > 1
        ? this.#axisSpanLabel(columnStart, columnEnd, columns.length, "x")
        : this.#geometricAxisLabel(item.frame.x, item.frame.width, "x");
    const vertical =
      rows.length > 1
        ? this.#axisSpanLabel(rowStart, rowEnd, rows.length, "y")
        : this.#geometricAxisLabel(item.frame.y, item.frame.height, "y");
    return {
      ...item,
      placement: {
        columnStart,
        columnEnd,
        columnSpan: columnEnd - columnStart + 1,
        rowStart,
        rowEnd,
        rowSpan: rowEnd - rowStart + 1,
        horizontal,
        vertical,
        semanticRegion: `${vertical} · ${horizontal}`,
      },
    };
  };
  /**
   * Derive tracks covered for the current rendered scene.
   * @param {number} start Start used by this operation.
   * @param {number} size Size used by this operation.
   * @param {SceneTrack[]} tracks Tracks used by this operation.
   * @returns {number[]} Captured tracksCovered evidence for the calling operation.
   */
  static #tracksCovered = (start, size, tracks) => {
    const end = start + size;
    const covered = tracks.flatMap((track, index) => {
      const intersection = Math.max(
        0,
        Math.min(end, track.end) - Math.max(start, track.start),
      );
      const centerInside = track.center >= start && track.center <= end;
      return intersection / Math.max(1e-9, track.size) >= 0.22 || centerInside
        ? [index]
        : [];
    });
    if (covered.length) return covered;
    const center = start + size / 2;
    return [
      tracks.reduce(
        (best, track, index) =>
          Math.abs(track.center - center) <
          Math.abs((tracks[best]?.center ?? center) - center)
            ? index
            : best,
        0,
      ),
    ];
  };
  /**
   * Derive spatial cells for the current rendered scene.
   * @param {ScenePlacement[]} placements Placements used by this operation.
   * @param {SceneTrack[]} columns Columns used by this operation.
   * @param {SceneTrack[]} rows Rows used by this operation.
   * @returns {SceneRecord[]} Captured spatialCells evidence for the calling operation.
   */
  static #spatialCells = (placements, columns, rows) =>
    rows.flatMap((row, rowIndex) =>
      columns.map((column, columnIndex) => {
        const frame = {
          x: column.start,
          y: row.start,
          width: column.size,
          height: row.size,
        };
        const occupants = placements.filter(
          ({ placement }) =>
            columnIndex >= placement.columnStart &&
            columnIndex <= placement.columnEnd &&
            rowIndex >= placement.rowStart &&
            rowIndex <= placement.rowEnd,
        );
        const stackingDensity = occupants.reduce(
          (sum, { frame: itemFrame }) => {
            const intersection = this.#frameIntersection(frame, itemFrame);
            return (
              sum +
              (intersection
                ? (intersection.width * intersection.height) /
                  Math.max(1e-9, frame.width * frame.height)
                : 0)
            );
          },
          0,
        );
        return {
          row: rowIndex,
          column: columnIndex,
          frame,
          semanticRegion: `${this.#axisTrackLabel(rowIndex, rows.length, "y")} · ${this.#axisTrackLabel(columnIndex, columns.length, "x")}`,
          occupancy:
            occupants.length === 0
              ? "empty"
              : occupants.length === 1
                ? "single"
                : "shared",
          alone: occupants.length === 1,
          occupants: occupants.map(({ sourceElementId }) => sourceElementId),
          coverage: this.#round(Math.min(1, stackingDensity)),
          stackingDensity: this.#round(stackingDensity),
        };
      }),
    );
  /**
   * Derive spatial alignment evidence for the current rendered scene.
   * @param {ScenePlacement[]} placements Placements used by this operation.
   * @param {SceneTrack[]} columns Columns used by this operation.
   * @param {SceneTrack[]} rows Rows used by this operation.
   * @returns {number} Captured spatialAlignmentEvidence evidence for the calling operation.
   */
  static #spatialAlignmentEvidence = (placements, columns, rows) => {
    if (!placements.length) return 0;
    const score = placements.reduce((sum, { frame, placement }) => {
      const columnCenter =
        ((columns[placement.columnStart]?.start ?? frame.x) +
          (columns[placement.columnEnd]?.end ?? frame.x + frame.width)) /
        2;
      const rowCenter =
        ((rows[placement.rowStart]?.start ?? frame.y) +
          (rows[placement.rowEnd]?.end ?? frame.y + frame.height)) /
        2;
      const itemCenterX = frame.x + frame.width / 2;
      const itemCenterY = frame.y + frame.height / 2;
      const horizontal =
        1 - this.#clamp(Math.abs(itemCenterX - columnCenter) * 3, 0, 1);
      const vertical =
        1 - this.#clamp(Math.abs(itemCenterY - rowCenter) * 3, 0, 1);
      return sum + (horizontal + vertical) / 2;
    }, 0);
    return score / placements.length;
  };
  /**
   * Derive axis track label for the current rendered scene.
   * @param {number} index Index used by this operation.
   * @param {number} count Count used by this operation.
   * @param {string} axis Axis used by this operation.
   * @returns {string} Captured axisTrackLabel evidence for the calling operation.
   */
  static #axisTrackLabel = (index, count, axis) => {
    if (count <= 1) return axis === "x" ? "full width" : "full height";
    if (count === 2)
      return axis === "x"
        ? (["left half", "right half"][index] ?? "horizontal half")
        : (["top half", "bottom half"][index] ?? "vertical half");
    if (count === 3)
      return axis === "x"
        ? (["left third", "center third", "right third"][index] ??
            "horizontal third")
        : (["top third", "middle third", "bottom third"][index] ??
            "vertical third");
    if (count === 4)
      return axis === "x"
        ? ([
            "first quarter",
            "second quarter",
            "third quarter",
            "fourth quarter",
          ][index] ?? "horizontal quarter")
        : ([
            "top quarter",
            "upper-middle quarter",
            "lower-middle quarter",
            "bottom quarter",
          ][index] ?? "vertical quarter");
    return `${axis === "x" ? "column" : "row"} ${index + 1} of ${count}`;
  };
  /**
   * Derive axis span label for the current rendered scene.
   * @param {number} start Start used by this operation.
   * @param {number} end End used by this operation.
   * @param {number} count Count used by this operation.
   * @param {string} axis Axis used by this operation.
   * @returns {string} Captured axisSpanLabel evidence for the calling operation.
   */
  static #axisSpanLabel = (start, end, count, axis) => {
    const span = end - start + 1;
    if (span >= count) return axis === "x" ? "full width" : "full height";
    if (count % 2 === 0 && span === count / 2) {
      if (axis === "x")
        return start === 0
          ? "left half"
          : end === count - 1
            ? "right half"
            : `middle ${span} of ${count} columns`;
      return start === 0
        ? "top half"
        : end === count - 1
          ? "bottom half"
          : `middle ${span} of ${count} rows`;
    }
    if (span === 1) return this.#axisTrackLabel(start, count, axis);
    return `${axis === "x" ? "columns" : "rows"} ${start + 1}–${end + 1} of ${count}`;
  };
  /**
   * Derive geometric axis label for the current rendered scene.
   * @param {number} start Start used by this operation.
   * @param {number} size Size used by this operation.
   * @param {string} axis Axis used by this operation.
   * @returns {string} Captured geometricAxisLabel evidence for the calling operation.
   */
  static #geometricAxisLabel = (start, size, axis) => {
    const center = start + size / 2;
    if (size >= 0.88) return axis === "x" ? "full width" : "full height";
    for (const denominator of [2, 3, 4]) {
      if (Math.abs(size - 1 / denominator) > 0.09) continue;
      const index = this.#clamp(
        Math.round(center * denominator - 0.5),
        0,
        denominator - 1,
      );
      const expectedCenter = (index + 0.5) / denominator;
      if (Math.abs(center - expectedCenter) <= 0.1)
        return this.#axisTrackLabel(index, denominator, axis);
    }
    if (axis === "x")
      return center < 0.34
        ? "left region"
        : center > 0.66
          ? "right region"
          : "center region";
    return center < 0.34
      ? "top region"
      : center > 0.66
        ? "bottom region"
        : "middle region";
  };
  static #selectorCache = new WeakMap();
  /**
   * Derive css length ratio for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {number} base Base used by this operation.
   * @returns {number} Captured cssLengthRatio evidence for the calling operation.
   */
  static #cssLengthRatio = (value, base) => {
    const text = String(value ?? "0").trim();
    if (!text || text === "normal" || text === "auto") return 0;
    if (text.endsWith("%")) return this.#round(parseFloat(text) / 100);
    const number = parseFloat(text);
    return Number.isFinite(number) ? this.#ratio(number, base) : 0;
  };
  /**
   * Derive parse color for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {?SceneRgba} Captured parseColor evidence for the calling operation.
   */
  static #parseColor = value => {
    if (!value || value === "transparent") return [0, 0, 0, 0];
    this.#colorCanvas ??= document.createElement("canvas");
    const canvas = this.#colorCanvas;
    canvas.width = 1;
    canvas.height = 1;
    const context = canvas.getContext("2d", {
      willReadFrequently: true,
    });
    if (!context) return null;
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = "rgba(0,0,0,0)";
    try {
      context.fillStyle = String(value);
    } catch {
      return null;
    }
    context.fillRect(0, 0, 1, 1);
    const data = context.getImageData(0, 0, 1, 1).data;
    return [data[0] ?? 0, data[1] ?? 0, data[2] ?? 0, (data[3] ?? 0) / 255];
  };
  /**
   * Derive color descriptor for the current rendered scene.
   * @param {?SceneRgba} color Color used by this operation.
   * @returns {?SceneColorDescriptor} Captured color description evidence for the calling operation.
   */
  static #colorDescriptor = color => {
    if (!color) return null;
    const rgba = /** @type {SceneRgba} */ ([
      Math.round(color[0]),
      Math.round(color[1]),
      Math.round(color[2]),
      this.#round(color[3]),
    ]);
    return {
      rgba,
      hex: `#${rgba
        .slice(0, 3)
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("")}`,
      luminance: this.#round(this.#relativeLuminance(rgba)),
    };
  };
  /**
   * Composite foreground RGBA over background RGBA.
   * @param {SceneRgba} foreground Foreground used by this operation.
   * @param {SceneRgba} background Background used by this operation.
   * @returns {SceneRgba} Captured alphaComposite evidence for the calling operation.
   */
  static #alphaComposite = (foreground, background) => {
    const fa = this.#clamp(foreground[3], 0, 1);
    const ba = this.#clamp(background[3], 0, 1);
    const alpha = fa + ba * (1 - fa);
    if (alpha <= 0) return [0, 0, 0, 0];
    return [
      (foreground[0] * fa + background[0] * ba * (1 - fa)) / alpha,
      (foreground[1] * fa + background[1] * ba * (1 - fa)) / alpha,
      (foreground[2] * fa + background[2] * ba * (1 - fa)) / alpha,
      alpha,
    ];
  };
  /**
   * Compute linear-light luminance from an sRGB color sample.
   * @param {SceneRgba} color Color used by this operation.
   * @returns {number} Captured relativeLuminance evidence for the calling operation.
   */
  static #relativeLuminance = color => {
    const channels = color.slice(0, 3).map(value => {
      const channel = value / 255;
      return channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return (
      (channels[0] ?? 0) * 0.2126 +
      (channels[1] ?? 0) * 0.7152 +
      (channels[2] ?? 0) * 0.0722
    );
  };
  /**
   * Compute relative contrast between the supplied luminance values.
   * @param {SceneRgba} a A used by this operation.
   * @param {SceneRgba} b B used by this operation.
   * @returns {number} Captured contrastRatio evidence for the calling operation.
   */
  static #contrastRatio = (a, b) => {
    const first = this.#relativeLuminance(a);
    const second = this.#relativeLuminance(b);
    const lighter = Math.max(first, second);
    const darker = Math.min(first, second);
    return (lighter + 0.05) / (darker + 0.05);
  };
  /**
   * Derive combined linear transform for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @returns {{matrix:DOMMatrixReadOnly|null,threeDimensional:boolean}} Captured combinedLinearTransform evidence for the calling operation.
   */
  static #combinedLinearTransform = style => {
    const parts = [];
    let threeDimensional = false;
    if (style.rotate && style.rotate !== "none") {
      const match = style.rotate.match(
        /^(?:(z)\s+)?(-?(?:\d+(?:\.\d+)?|\.\d+)(?:deg|grad|rad|turn))$/i,
      );
      if (match) parts.push(`rotate(${match[2]})`);
      else threeDimensional = true;
    }
    if (style.scale && style.scale !== "none") {
      const values = style.scale.trim().split(/\s+/).map(Number);
      if (values.every(Number.isFinite) && values.length <= 3) {
        const [x = 1, y = x, z = 1] = values;
        threeDimensional ||= z !== 1;
        if (!threeDimensional) parts.push(`scale(${x}, ${y})`);
      } else threeDimensional = true;
    }
    if (style.transform !== "none") parts.push(style.transform);
    if (!parts.length)
      return {
        matrix: null,
        threeDimensional,
      };
    try {
      const matrix = new globalThis.DOMMatrixReadOnly(parts.join(" "));
      return {
        matrix,
        threeDimensional: threeDimensional || !matrix.is2D,
      };
    } catch {
      return {
        matrix: null,
        threeDimensional: true,
      };
    }
  };
  /**
   * Derive individual transform descriptor for the current rendered scene.
   * @param {CSSStyleDeclaration} style Computed style snapshot for the current element.
   * @returns {{translate: ?string, rotate: ?string, scale: ?string} & SceneRecord} Captured individualTransform description evidence for the calling operation.
   */
  static #individualTransformDescriptor = style => ({
    translate:
      style.translate && style.translate !== "none" ? style.translate : null,
    rotate: style.rotate && style.rotate !== "none" ? style.rotate : null,
    scale: style.scale && style.scale !== "none" ? style.scale : null,
  });
  /**
   * Derive quad descriptor for the current rendered scene.
   * Uses the current DOM state; callers must refresh evidence after layout changes.
   * @param {Element} element Live DOM element observed or managed by this operation.
   * @param {DOMRectReadOnly} rect Measured rectangle in CSS pixels.
   * @param {DOMRectReadOnly} reference Reference geometry for coordinate normalization.
   * @returns {SceneQuad} Captured quad description evidence for the calling operation.
   */
  static #quadDescriptor = (element, rect, reference) => {
    /** @type {?ScenePoint[]} */
    let points = null;
    let source = null;
    let confidence = "high";
    try {
      const quad =
        /** @type {{getBoxQuads?: (options: {box: string}) => {p1:ScenePoint,p2:ScenePoint,p3:ScenePoint,p4:ScenePoint}[]}} */ (
          element
        ).getBoxQuads?.({
          box: "border",
        })?.[0];
      if (quad) {
        points = [quad.p1, quad.p2, quad.p3, quad.p4].map(({ x, y }) => ({
          x,
          y,
        }));
        source = "getBoxQuads-final-border-quad";
      }
    } catch {
      // Unsupported box-quad APIs fall back to computed transforms below.
    }
    if (!points) {
      const transforms = [];
      let threeDimensional = false;
      for (
        let current = /** @type {Element|null} */ (element);
        current instanceof Element;
        current = current.parentElement
      ) {
        const style = getComputedStyle(current);
        if (style.perspective !== "none") threeDimensional = true;
        const combined = this.#combinedLinearTransform(style);
        threeDimensional ||= combined.threeDimensional;
        if (combined.matrix) transforms.unshift(combined.matrix);
      }
      const width =
        element instanceof globalThis.SVGGraphicsElement
          ? (() => {
              try {
                return element.getBBox().width || rect.width;
              } catch {
                return rect.width;
              }
            })()
          : (element instanceof HTMLElement ? element.offsetWidth : 0) ||
            rect.width;
      const height =
        element instanceof globalThis.SVGGraphicsElement
          ? (() => {
              try {
                return element.getBBox().height || rect.height;
              } catch {
                return rect.height;
              }
            })()
          : (element instanceof HTMLElement ? element.offsetHeight : 0) ||
            rect.height;
      if (transforms.length && !threeDimensional && width && height) {
        const combined = transforms.reduce(
          (matrix, transform) => matrix.multiply(transform),
          new DOMMatrix(),
        );
        const top = {
          x: combined.a * width,
          y: combined.b * width,
        };
        const left = {
          x: combined.c * height,
          y: combined.d * height,
        };
        const relative = [
          {
            x: 0,
            y: 0,
          },
          top,
          {
            x: top.x + left.x,
            y: top.y + left.y,
          },
          left,
        ];
        const minX = Math.min(...relative.map(({ x }) => x));
        const minY = Math.min(...relative.map(({ y }) => y));
        points = relative.map(({ x, y }) => ({
          x: rect.left + x - minX,
          y: rect.top + y - minY,
        }));
        source = "computed-2d-transform-chain-plus-final-bounding-rect";
      } else {
        points = [
          {
            x: rect.left,
            y: rect.top,
          },
          {
            x: rect.right,
            y: rect.top,
          },
          {
            x: rect.right,
            y: rect.bottom,
          },
          {
            x: rect.left,
            y: rect.bottom,
          },
        ];
        source = threeDimensional
          ? "axis-aligned-fallback-3d-or-perspective"
          : "axis-aligned-bounding-rect";
        confidence = threeDimensional ? "reduced" : "high";
      }
    }
    const normalized = points.map(({ x, y }) => ({
      x: this.#ratio(x - reference.left, reference.width),
      y: this.#ratio(y - reference.top, reference.height),
    }));
    /**
     * Derive edge for the current rendered scene.
     * @param {ScenePoint} from From used by this operation.
     * @param {ScenePoint} to To used by this operation.
     * @returns {number} Euclidean distance between the two points.
     */
    const edge = (from, to) => Math.hypot(to.x - from.x, to.y - from.y);
    const fallbackPoint = {
      x: 0,
      y: 0,
    };
    const point0 = points[0] ?? fallbackPoint;
    const point1 = points[1] ?? fallbackPoint;
    const point2 = points[2] ?? fallbackPoint;
    const point3 = points[3] ?? fallbackPoint;
    const area = Math.abs(
      points.reduce((sum, point, index) => {
        const next = points[(index + 1) % points.length] ?? point;
        return sum + point.x * next.y - next.x * point.y;
      }, 0) / 2,
    );
    const topVector = {
      x: point1.x - point0.x,
      y: point1.y - point0.y,
    };
    const leftVector = {
      x: point3.x - point0.x,
      y: point3.y - point0.y,
    };
    const topLength = edge(point0, point1);
    const leftLength = edge(point0, point3);
    const dot = topVector.x * leftVector.x + topVector.y * leftVector.y;
    return {
      source,
      confidence,
      points: normalized,
      center: {
        x: this.#round(normalized.reduce((sum, point) => sum + point.x, 0) / 4),
        y: this.#round(normalized.reduce((sum, point) => sum + point.y, 0) / 4),
      },
      area: this.#ratio(area, reference.width * reference.height),
      edgeLengths: {
        top: this.#ratio(topLength, reference.width),
        right: this.#ratio(edge(point1, point2), reference.height),
        bottom: this.#ratio(edge(point2, point3), reference.width),
        left: this.#ratio(leftLength, reference.height),
      },
      orientationDegrees: this.#round(
        Math.atan2(topVector.y, topVector.x) * 180 / Math.PI,
        3,
      ),
      cornerAngleDegrees:
        topLength && leftLength
          ? this.#round(
              Math.acos(this.#clamp(dot / (topLength * leftLength), -1, 1)) *
                180 /
                Math.PI,
              3,
            )
          : null,
    };
  };
  /**
   * Derive matrix descriptor for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {DOMRectReadOnly} reference Reference geometry for coordinate normalization.
   * @returns {SceneMatrixDescriptor & SceneRecord | null} Captured matrix description evidence for the calling operation.
   */
  static #matrixDescriptor = (value, reference) => {
    if (!value || value === "none") return null;
    try {
      const matrix = new globalThis.DOMMatrixReadOnly(String(value));
      const scaleX = Math.hypot(matrix.a, matrix.b);
      const scaleY = Math.hypot(matrix.c, matrix.d);
      return {
        css: value,
        matrix2d: matrix.is2D
          ? {
              a: this.#round(matrix.a),
              b: this.#round(matrix.b),
              c: this.#round(matrix.c),
              d: this.#round(matrix.d),
              e: this.#ratio(matrix.e, reference.width),
              f: this.#ratio(matrix.f, reference.height),
            }
          : null,
        is2D: matrix.is2D,
        scale: {
          x: this.#round(scaleX),
          y: this.#round(scaleY),
        },
        rotationDegrees: matrix.is2D
          ? this.#round(Math.atan2(matrix.b, matrix.a) * 180 / Math.PI, 3)
          : null,
        determinant: this.#round(
          matrix.is2D ? matrix.a * matrix.d - matrix.b * matrix.c : 0,
        ),
        translation: {
          x: this.#ratio(matrix.m41, reference.width),
          y: this.#ratio(matrix.m42, reference.height),
          z: this.#ratio(
            matrix.m43,
            Math.max(reference.width, reference.height),
          ),
        },
      };
    } catch {
      return {
        css: value,
        parseable: false,
      };
    }
  };
  /**
   * Derive object polygon for the current rendered scene.
   * @param {SceneObject} object Object used by this operation.
   * @returns {{x:number,y:number}[]} Captured objectPolygon evidence for the calling operation.
   */
  static #objectPolygon = object => {
    const quad = /** @type {{points?: {x:number,y:number}[]}|undefined} */ (
      /** @type {unknown} */
      (object.transform[String("finalQuad")])
    );
    return quad?.points?.length === 4
      ? quad.points
      : [
          {
            x: object.frame.x,
            y: object.frame.y,
          },
          {
            x: object.frame.x + object.frame.width,
            y: object.frame.y,
          },
          {
            x: object.frame.x + object.frame.width,
            y: object.frame.y + object.frame.height,
          },
          {
            x: object.frame.x,
            y: object.frame.y + object.frame.height,
          },
        ];
  };
  /**
   * Derive signed polygon area for the current rendered scene.
   * @param {Array<{x: number, y: number}>} polygon Polygon used by this operation.
   * @returns {number} Captured signedPolygonArea evidence for the calling operation.
   */
  static #signedPolygonArea = polygon =>
    polygon.length < 3
      ? 0
      : polygon.reduce((sum, point, index) => {
          const next = polygon[(index + 1) % polygon.length] ?? point;
          return sum + point.x * next.y - next.x * point.y;
        }, 0) / 2;
  /**
   * Derive polygon area for the current rendered scene.
   * @param {Array<{x: number, y: number}>} polygon Polygon used by this operation.
   * @returns {number} Captured polygonArea evidence for the calling operation.
   */
  static #polygonArea = polygon => Math.abs(this.#signedPolygonArea(polygon));
  /**
   * Derive cross2 for the current rendered scene.
   * @param {ScenePoint} a A used by this operation.
   * @param {ScenePoint} b B used by this operation.
   * @returns {number} Captured cross2 evidence for the calling operation.
   */
  static #cross2 = (a, b) => a.x * b.y - a.y * b.x;
  /**
   * Derive polygon intersection point for the current rendered scene.
   * @param {ScenePoint} start Start used by this operation.
   * @param {ScenePoint} end End used by this operation.
   * @param {ScenePoint} clipStart Clipstart used by this operation.
   * @param {ScenePoint} clipEnd Clipend used by this operation.
   * @returns {{x:number,y:number}} Captured polygonIntersectionPoint evidence for the calling operation.
   */
  static #polygonIntersectionPoint = (start, end, clipStart, clipEnd) => {
    const segment = {
      x: end.x - start.x,
      y: end.y - start.y,
    };
    const edge = {
      x: clipEnd.x - clipStart.x,
      y: clipEnd.y - clipStart.y,
    };
    const denominator = this.#cross2(segment, edge);
    if (Math.abs(denominator) <= 1e-12) return end;
    const offset = {
      x: clipStart.x - start.x,
      y: clipStart.y - start.y,
    };
    const t = this.#cross2(offset, edge) / denominator;
    return {
      x: this.#round(start.x + segment.x * t, 6),
      y: this.#round(start.y + segment.y * t, 6),
    };
  };
  /**
   * Clip a polygon against another polygon to describe overlap.
   * @param {Array<{x: number, y: number}>} subject Subject used by this operation.
   * @param {Array<{x: number, y: number}>} clip Clip used by this operation.
   * @returns {{x:number,y:number}[]} Captured polygonIntersection evidence for the calling operation.
   */
  static #polygonIntersection = (subject, clip) => {
    if (subject.length < 3 || clip.length < 3) return [];
    const orientation = Math.sign(this.#signedPolygonArea(clip)) || 1;
    /**
     * Derive inside for the current rendered scene.
     * @param {ScenePoint} point Point used by this operation.
     * @param {ScenePoint} start Start used by this operation.
     * @param {ScenePoint} end End used by this operation.
     * @returns {boolean} Whether the point is inside the edge.
     */
    const inside = (point, start, end) =>
      orientation *
        this.#cross2(
          {
            x: end.x - start.x,
            y: end.y - start.y,
          },
          {
            x: point.x - start.x,
            y: point.y - start.y,
          },
        ) >=
      -1e-9;
    let output = subject.map(({ x, y }) => ({
      x,
      y,
    }));
    for (let index = 0; index < clip.length && output.length; index++) {
      const clipStart = clip[index];
      const clipEnd = clip[(index + 1) % clip.length];
      if (!clipStart || !clipEnd) continue;
      const input = output;
      output = [];
      let start = input.at(-1);
      if (!start) continue;
      for (const end of input) {
        const endInside = inside(end, clipStart, clipEnd);
        const startInside = inside(start, clipStart, clipEnd);
        if (endInside) {
          if (!startInside)
            output.push(
              this.#polygonIntersectionPoint(start, end, clipStart, clipEnd),
            );
          output.push(end);
        } else if (startInside)
          output.push(
            this.#polygonIntersectionPoint(start, end, clipStart, clipEnd),
          );
        start = end;
      }
    }
    return output.map(({ x, y }) => ({
      x: this.#round(x, 6),
      y: this.#round(y, 6),
    }));
  };
  /**
   * Derive polygon bounds for the current rendered scene.
   * @param {Array<{x: number, y: number}>} polygon Polygon used by this operation.
   * @returns {SceneRecord} Captured polygonBounds evidence for the calling operation.
   */
  static #polygonBounds = polygon => {
    const xs = polygon.map(({ x }) => x);
    const ys = polygon.map(({ y }) => y);
    const left = Math.min(...xs);
    const top = Math.min(...ys);
    const right = Math.max(...xs);
    const bottom = Math.max(...ys);
    return {
      x: this.#round(left),
      y: this.#round(top),
      width: this.#round(right - left),
      height: this.#round(bottom - top),
    };
  };
  /**
   * Derive ratio for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {number} base Base used by this operation.
   * @returns {number} Captured ratio evidence for the calling operation.
   */
  static #ratio = (value, base) =>
    base ? this.#round(Number(value) / base) : 0;
  /**
   * Derive round for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {number} [precision] Precision used by this operation.
   * @returns {number} Captured round evidence for the calling operation.
   */
  static #round = (value, precision = 4) =>
    Number(Number(value).toFixed(precision));
  /**
   * Derive clamp for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {number} min Min used by this operation.
   * @param {number} max Max used by this operation.
   * @returns {number} Captured clamp evidence for the calling operation.
   */
  static #clamp = (value, min, max) =>
    Math.min(max, Math.max(min, Number(value)));
  /** @type {HTMLCanvasElement|null} */
  static #colorCanvas = null;
}
/** @type {Record<string, unknown>} */ (globalThis)[String("Descriptor")] =
  Descriptor;
/**
 * Provide Scene Binary Bundle scene-evidence operations.
 *
 * @class SceneBinaryBundle Encodes scene manifests and captured binary assets.
 */
class SceneBinaryBundle {
  static #mimeExtensions = /** @type {Record<string, string>} */ ({
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "application/pdf": "pdf",
    "application/octet-stream": "bin",
    "font/woff": "woff",
    "font/woff2": "woff2",
    "font/ttf": "ttf",
    "font/otf": "otf",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
  });
  static #encoder = new TextEncoder();
  static #crcTable = Array.from(
    {
      length: 256,
    },
    (_, index) => {
      let crc = index;
      for (let bit = 0; bit < 8; bit += 1)
        crc = crc & 1 ? 0xedb88320 ^ crc >>> 1 : crc >>> 1;
      return crc >>> 0;
    },
  );
  /**
   * Derive hex for the current rendered scene.
   * @param {ArrayBuffer} buffer Buffer used by this operation.
   * @returns {string} Captured hex evidence for the calling operation.
   */
  static #hex = buffer =>
    [...new Uint8Array(buffer)]
      .map(byte => byte.toString(16).padStart(2, "0"))
      .join("");
  /**
   * Derive extension for the current rendered scene.
   * @param {string} mime Mime used by this operation.
   * @returns {string} Captured extension evidence for the calling operation.
   */
  static #extension = mime =>
    this.#mimeExtensions[mime.toLowerCase()] ??
    (mime
      .split("/")[1]
      ?.split(/[;+]/)[0]
      ?.replace(/[^a-z0-9]/gi, "") ||
      "bin");
  /**
   * Derive data uri blob for the current rendered scene.
   * @param {string} uri Uri used by this operation.
   * @returns {Blob} Captured dataUriBlob evidence for the calling operation.
   */
  static #dataUriBlob = uri => {
    const match = /^data:([^;,]*)(;base64)?,(.*)$/s.exec(uri);
    if (!match) throw new TypeError("Invalid data URI.");
    return new Blob(
      [
        match[2]
          ? Uint8Array.from(atob(match[3] ?? ""), character =>
              character.charCodeAt(0),
            )
          : this.#encoder.encode(decodeURIComponent(match[3] ?? "")),
      ],
      {
        type: match[1] || "application/octet-stream",
      },
    );
  };
  /**
   * Derive reference for the current rendered scene.
   * @param {Blob} blob Blob used by this operation.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<SceneRecord>} Captured reference evidence for the calling operation.
   */
  static #reference = async (blob, files) => {
    const sha256 = this.#hex(
      await /** @type {{__evidenceSha256: (buffer: ArrayBuffer) => Promise<ArrayBuffer>}} */ (
        /** @type {unknown} */ (globalThis)
      ).__evidenceSha256(await blob.arrayBuffer()),
    );
    const file = `sha256-${sha256}.${this.#extension(blob.type || "application/octet-stream")}`;
    files.has(file) || files.set(file, blob);
    return {
      file,
      sha256,
      mime: blob.type || "application/octet-stream",
      bytes: blob.size,
    };
  };
  /**
   * Derive contains data uri for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {boolean} Captured containsDataUri evidence for the calling operation.
   */
  static #containsDataUri = value =>
    typeof value === "string"
      ? value.startsWith("data:")
      : Array.isArray(value)
        ? value.some(this.#containsDataUri)
        : Boolean(
            value &&
            typeof value === "object" &&
            Object.values(value).some(this.#containsDataUri),
          );
  /**
   * Replace embedded data URIs with deduplicated binary-file references.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @param {Map<string, SceneValue>} cache Cache used by this operation.
   * @returns {Promise<SceneValue>} Captured externalize evidence for the calling operation.
   */
  static #externalize = async (value, files, cache) => {
    if (typeof value === "string" && value.startsWith("data:")) {
      if (cache.has(value)) return cache.get(value) ?? null;
      const reference = await this.#reference(this.#dataUriBlob(value), files);
      cache.set(value, reference);
      return reference;
    }
    if (Array.isArray(value))
      return Promise.all(
        value.map(item => this.#externalize(item, files, cache)),
      );
    return !value || typeof value !== "object"
      ? value
      : Object.fromEntries(
          await Promise.all(
            Object.entries(/** @type {Record<string, unknown>} */ (value)).map(
              async ([key, item]) =>
                /** @type {[string, SceneValue]} */ ([
                  key,
                  await this.#externalize(item, files, cache),
                ]),
            ),
          ),
        );
  };
  /**
   * Separate a scene manifest from binary assets for export.
   * @param {SceneRecord} scene Scene used by this operation.
   * @returns {Promise<{manifest:SceneRecord,files:Map<string,Blob>}>} Captured create evidence for the calling operation.
   */
  static create = async scene => {
    const files = /** @type {Map<string, Blob>} */ (new Map());
    const manifest = /** @type {SceneRecord} */ (
      this.#containsDataUri(scene)
        ? await this.#externalize(scene, files, new Map())
        : {
            ...scene,
          }
    );
    manifest[String("binaryFiles")] = [...files.entries()].map(
      ([file, blob]) => ({
        file,
        mime: blob.type || "application/octet-stream",
        bytes: blob.size,
      }),
    );
    return {
      manifest,
      files,
    };
  };
  /**
   * Compute the CRC-32 checksum used by ZIP file entries.
   * @param {Uint8Array} bytes Bytes used by this operation.
   * @returns {number} Captured crc32 evidence for the calling operation.
   */
  static #crc32 = bytes => {
    let crc = 0xffffffff;
    for (const byte of bytes)
      crc = (this.#crcTable[(crc ^ byte) & 0xff] ?? 0) ^ crc >>> 8;
    return (crc ^ 0xffffffff) >>> 0;
  };
  /**
   * Derive u16 for the current rendered scene.
   * @param {number} value Value read from the current DOM, configuration or serialized scene.
   * @returns {Uint8Array<ArrayBuffer>} Captured u16 evidence for the calling operation.
   */
  static #u16 = value => new Uint8Array([value & 255, value >>> 8 & 255]);
  /**
   * Derive u32 for the current rendered scene.
   * @param {number} value Value read from the current DOM, configuration or serialized scene.
   * @returns {Uint8Array<ArrayBuffer>} Captured u32 evidence for the calling operation.
   */
  static #u32 = value =>
    new Uint8Array([
      value & 255,
      value >>> 8 & 255,
      value >>> 16 & 255,
      value >>> 24 & 255,
    ]);
  /**
   * Copy byte-array parts into a single contiguous buffer.
   * @param {Uint8Array[]} parts Parts used by this operation.
   * @returns {Uint8Array<ArrayBuffer>} Captured concat evidence for the calling operation.
   */
  static #concat = parts => {
    const output = new Uint8Array(
      parts.reduce((sum, part) => sum + part.length, 0),
    );
    let offset = 0;
    for (const part of parts) {
      output.set(part, offset);
      offset += part.length;
    }
    return output;
  };
  /**
   * Derive dos time for the current rendered scene.
   * @param {Date} [date] Date used by this operation.
   * @returns {{time:number,date:number}} Captured dosTime evidence for the calling operation.
   */
  static #dosTime = (date = new Date()) => ({
    time:
      date.getHours() << 11 |
      date.getMinutes() << 5 |
      date.getSeconds() >> 1,
    date:
      date.getFullYear() - 1980 << 9 |
      date.getMonth() + 1 << 5 |
      date.getDate(),
  });
  /**
   * Encode a manifest and binary assets as a ZIP archive.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<Blob>} Captured zip evidence for the calling operation.
   */
  static zip = async (manifest, files) => {
    const entries = /** @type {[string, Blob][]} */ ([
      [
        "scene.json",
        new Blob([JSON.stringify(manifest, null, 2)], {
          type: "application/json",
        }),
      ],
      ...files,
    ]);
    const locals = [];
    const centrals = [];
    let offset = 0;
    const { time, date } = this.#dosTime();
    const prepared = await Promise.all(
      entries.map(async ([name, blob]) => {
        const nameBytes = this.#encoder.encode(name);
        const bytes = new Uint8Array(await blob.arrayBuffer());
        return {
          nameBytes,
          bytes,
          crc: this.#crc32(bytes),
        };
      }),
    );
    for (const { nameBytes, bytes, crc } of prepared) {
      const local = this.#concat([
        this.#u32(0x04034b50),
        this.#u16(20),
        this.#u16(0x0800),
        this.#u16(0),
        this.#u16(time),
        this.#u16(date),
        this.#u32(crc),
        this.#u32(bytes.length),
        this.#u32(bytes.length),
        this.#u16(nameBytes.length),
        this.#u16(0),
        nameBytes,
        bytes,
      ]);
      locals.push(local);
      centrals.push(
        this.#concat([
          this.#u32(0x02014b50),
          this.#u16(20),
          this.#u16(20),
          this.#u16(0x0800),
          this.#u16(0),
          this.#u16(time),
          this.#u16(date),
          this.#u32(crc),
          this.#u32(bytes.length),
          this.#u32(bytes.length),
          this.#u16(nameBytes.length),
          this.#u16(0),
          this.#u16(0),
          this.#u16(0),
          this.#u16(0),
          this.#u32(0),
          this.#u32(offset),
          nameBytes,
        ]),
      );
      offset += local.length;
    }
    const central = this.#concat(centrals);
    return new Blob(
      [
        ...locals,
        central,
        this.#concat([
          this.#u32(0x06054b50),
          this.#u16(0),
          this.#u16(0),
          this.#u16(entries.length),
          this.#u16(entries.length),
          this.#u32(central.length),
          this.#u32(offset),
          this.#u16(0),
        ]),
      ],
      {
        type: "application/zip",
      },
    );
  };
  /**
   * Derive tar octal for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {number} length Length used by this operation.
   * @returns {string} Captured tarOctal evidence for the calling operation.
   */
  static #tarOctal = (value, length) =>
    `${Math.max(0, Number(value))
      .toString(8)
      .padStart(length - 1, "0")}\0`.slice(-length);
  /**
   * Derive tar header for the current rendered scene.
   * @param {string} name Name used by this operation.
   * @param {number} size Size used by this operation.
   * @param {Date} [date] Date used by this operation.
   * @returns {Uint8Array<ArrayBuffer>} Captured tarHeader evidence for the calling operation.
   */
  static #tarHeader = (name, size, date = new Date()) => {
    const header = new Uint8Array(512);
    /** Write an encoded value into the tar header at the given offset.
     * @param {number} offset Byte offset in the header.
     * @param {number} length Maximum byte length to write.
     * @param {string} value String value to encode and write.
     * @returns {void}
     */
    const write = (offset, length, value) =>
      header.set(this.#encoder.encode(value).subarray(0, length), offset);
    /**
     * Derive write for the current rendered scene.
     * @param {number} offset Offset used by this operation.
     * @param {number} length Length used by this operation.
     * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
     */
    write(0, 100, name);
    write(100, 8, this.#tarOctal(0o644, 8));
    write(108, 8, this.#tarOctal(0, 8));
    write(116, 8, this.#tarOctal(0, 8));
    write(124, 12, this.#tarOctal(size, 12));
    write(136, 12, this.#tarOctal(Math.floor(date.getTime() / 1000), 12));
    header.fill(32, 148, 156);
    header[156] = 48;
    write(257, 6, "ustar\0");
    write(263, 2, "00");
    write(265, 32, "browser");
    write(297, 32, "browser");
    write(
      148,
      8,
      `${header
        .reduce((sum, byte) => sum + byte, 0)
        .toString(8)
        .padStart(6, "0")}\0 `,
    );
    return header;
  };
  /**
   * Derive tar for the current rendered scene.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Blob} Captured tar evidence for the calling operation.
   */
  static tar = (manifest, files) => {
    const date = new Date();
    return new Blob(
      [
        .../** @type {[string, Blob][]} */ ([
          [
            "scene.json",
            new Blob([JSON.stringify(manifest, null, 2)], {
              type: "application/json",
            }),
          ],
          ...files,
        ]).flatMap(([name, blob]) => [
          this.#tarHeader(name, blob.size, date),
          blob,
          new Uint8Array((512 - blob.size % 512) % 512),
        ]),
        new Uint8Array(1024),
      ],
      {
        type: "application/x-tar",
      },
    );
  };
  /**
   * Derive be for the current rendered scene.
   * @param {number} bytes Bytes used by this operation.
   * @param {"setUint16"|"setUint32"|"setFloat64"|"setInt16"|"setInt32"} setter Setter used by this operation.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @returns {Uint8Array<ArrayBuffer>} Captured be evidence for the calling operation.
   */
  static #be = (bytes, setter, value) => {
    const output = new Uint8Array(bytes);
    new DataView(output.buffer)[setter](0, Number(value), false);
    return output;
  };
  /**
   * Derive mp length for the current rendered scene.
   * @param {number} length Length used by this operation.
   * @param {number} fixedLimit Fixedlimit used by this operation.
   * @param {number} fixedBase Fixedbase used by this operation.
   * @param {?number} code8 Code8 used by this operation.
   * @param {?number} code16 Code16 used by this operation.
   * @param {?number} code32 Code32 used by this operation.
   * @returns {Uint8Array<ArrayBuffer>} Captured mpLength evidence for the calling operation.
   */
  static #mpLength = (length, fixedLimit, fixedBase, code8, code16, code32) =>
    length <= fixedLimit
      ? Uint8Array.of(fixedBase | length)
      : code8 !== null && length <= 0xff
        ? Uint8Array.of(code8, length)
        : length <= 0xffff
          ? this.#concat([
              Uint8Array.of(Number(code16)),
              this.#be(2, "setUint16", length),
            ])
          : this.#concat([
              Uint8Array.of(Number(code32)),
              this.#be(4, "setUint32", length),
            ]);
  /**
   * Derive mp number for the current rendered scene.
   * @param {number} value Value read from the current DOM, configuration or serialized scene.
   * @returns {Uint8Array<ArrayBuffer>} Captured mpNumber evidence for the calling operation.
   */
  static #mpNumber = value => {
    if (!Number.isInteger(value) || !Number.isSafeInteger(value))
      return this.#concat([
        Uint8Array.of(0xcb),
        this.#be(8, "setFloat64", value),
      ]);
    if (value >= 0)
      return value <= 0x7f
        ? Uint8Array.of(value)
        : value <= 0xff
          ? Uint8Array.of(0xcc, value)
          : value <= 0xffff
            ? this.#concat([
                Uint8Array.of(0xcd),
                this.#be(2, "setUint16", value),
              ])
            : value <= 0xffffffff
              ? this.#concat([
                  Uint8Array.of(0xce),
                  this.#be(4, "setUint32", value),
                ])
              : this.#concat([
                  Uint8Array.of(0xcb),
                  this.#be(8, "setFloat64", value),
                ]);
    return value >= -32
      ? Uint8Array.of(0x100 + value)
      : value >= -128
        ? Uint8Array.of(0xd0, 0x100 + value)
        : value >= -32768
          ? this.#concat([Uint8Array.of(0xd1), this.#be(2, "setInt16", value)])
          : value >= -2147483648
            ? this.#concat([
                Uint8Array.of(0xd2),
                this.#be(4, "setInt32", value),
              ])
            : this.#concat([
                Uint8Array.of(0xcb),
                this.#be(8, "setFloat64", value),
              ]);
  };
  /**
   * Derive mp encode for the current rendered scene.
   * @param {unknown} value Value read from the current DOM, configuration or serialized scene.
   * @param {Uint8Array[]} parts Parts used by this operation.
   * @returns {void} Updates the capture context in place.
   */
  static #mpEncode = (value, parts) => {
    if (value === null) parts.push(Uint8Array.of(0xc0));
    else if (typeof value === "boolean")
      parts.push(Uint8Array.of(value ? 0xc3 : 0xc2));
    else if (typeof value === "number") parts.push(this.#mpNumber(value));
    else if (typeof value === "string") {
      const bytes = this.#encoder.encode(value);
      parts.push(
        this.#mpLength(bytes.length, 31, 0xa0, 0xd9, 0xda, 0xdb),
        bytes,
      );
    } else if (value instanceof Uint8Array)
      parts.push(
        value.length <= 0xff
          ? Uint8Array.of(0xc4, value.length)
          : value.length <= 0xffff
            ? this.#concat([
                Uint8Array.of(0xc5),
                this.#be(2, "setUint16", value.length),
              ])
            : this.#concat([
                Uint8Array.of(0xc6),
                this.#be(4, "setUint32", value.length),
              ]),
        value,
      );
    else if (value instanceof ArrayBuffer || ArrayBuffer.isView(value))
      this.#mpEncode(
        value instanceof ArrayBuffer
          ? new Uint8Array(value)
          : new Uint8Array(value.buffer, value.byteOffset, value.byteLength),
        parts,
      );
    else if (Array.isArray(value)) {
      parts.push(this.#mpLength(value.length, 15, 0x90, null, 0xdc, 0xdd));
      value.forEach(item => {
        this.#mpEncode(item, parts);
      });
    } else if (value && typeof value === "object") {
      const entries = Object.entries(value);
      parts.push(this.#mpLength(entries.length, 15, 0x80, null, 0xde, 0xdf));
      entries.forEach(([key, item]) => {
        this.#mpEncode(key, parts);
        this.#mpEncode(item, parts);
      });
    } else
      throw new TypeError(`Unsupported MessagePack value: ${typeof value}`);
  };
  /**
   * Encode a scene manifest and binary assets using MessagePack.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<Blob>} Captured messagePack evidence for the calling operation.
   */
  static messagePack = async (manifest, files) => {
    const parts = /** @type {Uint8Array[]} */ ([]);
    this.#mpEncode(
      {
        format: "dom-visual-scene-bundle",
        version: 1,
        manifest,
        files: Object.fromEntries(
          await Promise.all(
            [...files].map(async ([name, blob]) => [
              name,
              new Uint8Array(await blob.arrayBuffer()),
            ]),
          ),
        ),
      },
      parts,
    );
    return new Blob(
      parts.map(part => new Uint8Array(part)),
      {
        type: "application/msgpack",
      },
    );
  };
  /**
   * Derive compression supported for the current rendered scene.
   * @param {string} format Format used by this operation.
   * @returns {boolean} Captured compressionSupported evidence for the calling operation.
   */
  static compressionSupported = format => {
    if (typeof globalThis.CompressionStream !== "function") return false;
    try {
      return Boolean(
        new globalThis.CompressionStream(
          /** @type {CompressionFormat} */ (format),
        ),
      );
    } catch {
      return false;
    }
  };
  /**
   * Compress a blob using the browser compression stream API.
   * @param {Blob} blob Blob used by this operation.
   * @param {string} format Format used by this operation.
   * @param {string} mime Mime used by this operation.
   * @returns {Promise<Blob>} Captured compress evidence for the calling operation.
   */
  static #compress = async (blob, format, mime) => {
    if (!this.compressionSupported(format))
      throw new Error(
        `This browser does not support native ${format} compression.`,
      );
    const compressed = await new Response(
      blob
        .stream()
        .pipeThrough(
          new globalThis.CompressionStream(
            /** @type {CompressionFormat} */ (format),
          ),
        ),
    ).blob();
    return compressed.slice(0, compressed.size, mime);
  };
  /**
   * Derive gzip for the current rendered scene.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<Blob>} Captured gzip evidence for the calling operation.
   */
  static gzip = (manifest, files) =>
    this.#compress(this.tar(manifest, files), "gzip", "application/gzip");
  /**
   * Derive brotli for the current rendered scene.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<Blob>} Captured brotli evidence for the calling operation.
   */
  static brotli = async (manifest, files) =>
    this.#compress(
      await this.messagePack(manifest, files),
      "brotli",
      "application/octet-stream",
    );
  /**
   * Derive zstd store for the current rendered scene.
   * @param {Uint8Array<ArrayBuffer>} bytes Bytes used by this operation.
   * @returns {Blob} Captured zstdStore evidence for the calling operation.
   */
  static #zstdStore = bytes =>
    new Blob(
      [
        Uint8Array.of(0x28, 0xb5, 0x2f, 0xfd, 0xa0),
        this.#u32(bytes.length),
        ...Array.from(
          {
            length: Math.max(1, Math.ceil(bytes.length / 131072)),
          },
          (_, index) => {
            const chunk = bytes.subarray(
              index * 131072,
              Math.min(bytes.length, (index + 1) * 131072),
            );
            const header =
              chunk.length << 3 |
              Number((index + 1) * 131072 >= bytes.length);
            return [
              Uint8Array.of(
                header & 255,
                header >>> 8 & 255,
                header >>> 16 & 255,
              ),
              chunk,
            ];
          },
        ).flat(),
      ],
      {
        type: "application/zstd",
      },
    );
  /**
   * Derive zstd for the current rendered scene.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @returns {Promise<Blob>} Captured zstd evidence for the calling operation.
   */
  static zstd = async (manifest, files) => {
    const messagePack = await this.messagePack(manifest, files);
    return this.compressionSupported("zstd")
      ? this.#compress(messagePack, "zstd", "application/zstd")
      : this.#zstdStore(new Uint8Array(await messagePack.arrayBuffer()));
  };
  /**
   * Derive label for the current rendered scene.
   * @param {string} format Format used by this operation.
   * @returns {string} Captured label evidence for the calling operation.
   */
  static label = format =>
    /** @type {Record<string, string>} */ ({
      zip: "JSON + ZIP",
      gzip: "JSON + TAR.GZ",
      msgpack: "MessagePack",
      "msgpack-brotli": "MessagePack + Brotli",
      "msgpack-zstd": "MessagePack + Zstd",
    })[format] ?? format;
  /**
   * Encode the chosen archive format and trigger its browser download.
   * @param {SceneRecord} manifest Serializable scene description associated with the binary assets.
   * @param {Map<string, Blob>} files Archive entries accumulated or consumed by the export operation.
   * @param {string} [format] Format used by this operation.
   * Side effects: Writes to the clipboard or initiates a download after capture.
   * Failure: Unsupported browser APIs or failed encoding reject the request.
   * @returns {Promise<{blob:Blob,file:string}>} Captured download evidence for the calling operation.
   */
  static download = async (manifest, files, format = "zip") => {
    const output =
      /** @type {Record<string, [() => Promise<Blob>, string]>} */ ({
        zip: [() => this.zip(manifest, files), "zip"],
        gzip: [() => this.gzip(manifest, files), "tar.gz"],
        msgpack: [() => this.messagePack(manifest, files), "msgpack"],
        "msgpack-brotli": [() => this.brotli(manifest, files), "msgpack.br"],
        "msgpack-zstd": [() => this.zstd(manifest, files), "msgpack.zst"],
      })[format];
    if (!output) throw new TypeError(`Unsupported bundle format: ${format}`);
    const blob = await output[0]();
    const file = `visual-scene-bundle.${output[1]}`;
    const url = URL.createObjectURL(blob);
    Object.assign(document.createElement("a"), {
      href: url,
      download: file,
    }).click();
    queueMicrotask(() => URL.revokeObjectURL(url));
    return {
      blob,
      file,
    };
  };
}
/** @type {Record<string, unknown>} */ (globalThis)[
  String("SceneBinaryBundle")
] = SceneBinaryBundle;
/* Unified rolling video, image capture, scene description and evidence API. */
(() => {
  "use strict";
  /**
   * Hash binary input with SHA-256, falling back to a software implementation.
   * @param {ArrayBuffer | Uint8Array<ArrayBuffer>} input Binary input to hash.
   * @returns {Promise<ArrayBuffer>} Resolves with the SHA-256 digest.
   */
  const evidenceSha256 = async input => {
    if (globalThis.crypto?.subtle?.digest)
      return globalThis.crypto.subtle.digest("SHA-256", input);
    const bytes =
      input instanceof ArrayBuffer
        ? new Uint8Array(input)
        : new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
    const bitLength = bytes.length * 8;
    const paddedLength = bytes.length + 9 + 63 & ~63;
    const data = new Uint8Array(paddedLength);
    data.set(bytes);
    data[bytes.length] = 128;
    const view = new DataView(data.buffer);
    const high = Math.floor(bitLength / 0x100000000);
    const low = bitLength >>> 0;
    view.setUint32(paddedLength - 8, high, false);
    view.setUint32(paddedLength - 4, low, false);
    const constants = new Uint32Array([
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
      0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
      0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
      0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
      0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
      0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
      0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
      0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
      0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]);
    const hash = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
      0x1f83d9ab, 0x5be0cd19,
    ]);
    const words = new Uint32Array(64);
    /**
     * Rotate a 32-bit word right by the given count.
     * @param {number} value Word to rotate.
     * @param {number} count Bit count to rotate by.
     * @returns {number} Rotated word.
     */
    const rotate = (value, count) =>
      (value >>> count) | value << 32 - count;
    for (let offset = 0; offset < data.length; offset += 64) {
      for (let index = 0; index < 16; index++)
        words[index] = view.getUint32(offset + index * 4, false);
      for (let index = 16; index < 64; index++) {
        const x = words[index - 15] ?? 0;
        const y = words[index - 2] ?? 0;
        const s0 = rotate(x, 7) ^ rotate(x, 18) ^ x >>> 3;
        const s1 = rotate(y, 17) ^ rotate(y, 19) ^ y >>> 10;
        words[index] =
          (words[index - 16] ?? 0) + s0 + (words[index - 7] ?? 0) + s1 >>> 0;
      }
      let [a = 0, b = 0, c = 0, d = 0, e = 0, f = 0, g = 0, h = 0] = hash;
      for (let index = 0; index < 64; index++) {
        const s1 = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
        const choice = e & f ^ ~e & g;
        const temp1 =
          h + s1 + choice + (constants[index] ?? 0) + (words[index] ?? 0) >>>
          0;
        const s0 = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
        const majority = a & b ^ a & c ^ b & c;
        const temp2 = s0 + majority >>> 0;
        h = g;
        g = f;
        f = e;
        e = d + temp1 >>> 0;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2 >>> 0;
      }
      hash[0] = (hash[0] ?? 0) + a >>> 0;
      hash[1] = (hash[1] ?? 0) + b >>> 0;
      hash[2] = (hash[2] ?? 0) + c >>> 0;
      hash[3] = (hash[3] ?? 0) + d >>> 0;
      hash[4] = (hash[4] ?? 0) + e >>> 0;
      hash[5] = (hash[5] ?? 0) + f >>> 0;
      hash[6] = (hash[6] ?? 0) + g >>> 0;
      hash[7] = (hash[7] ?? 0) + h >>> 0;
    }
    const output = new Uint8Array(32);
    const outputView = new DataView(output.buffer);
    hash.forEach((value, index) => {
      outputView.setUint32(index * 4, value, false);
    });
    return output.buffer;
  };
  /** @type {Record<string, unknown>} */ (globalThis)[
    String("__evidenceSha256")
  ] = evidenceSha256;
  /**
   * Handle evidence Id for scene-evidence processing.
   * @returns {SceneValue} The resulting value.
   */
  const evidenceId = () => {
    const bytes = new Uint8Array(16);
    globalThis.crypto?.getRandomValues?.(bytes);
    if (!bytes.some(Boolean))
      for (let index = 0; index < bytes.length; index++)
        bytes[index] = Math.floor(Math.random() * 256);
    bytes[6] = (bytes[6] ?? 0) & 15 | 64;
    bytes[8] = (bytes[8] ?? 0) & 63 | 128;
    const hex = [...bytes].map(byte => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  };
  /**
   * Provide Rolling Capture scene-evidence operations.
   */
  class RollingCapture extends EventTarget {
    static qualities = /** @type {Readonly<Record<string, RollingQuality>>} */ (
      Object.freeze({
        low: {
          fps: 15,
          videoBitsPerSecond: 750000,
        },
        medium: {
          fps: 30,
          videoBitsPerSecond: 2500000,
        },
        high: {
          fps: 60,
          videoBitsPerSecond: 6000000,
        },
        ultra: {
          fps: 60,
          videoBitsPerSecond: 12000000,
        },
      })
    );
    static mimeTypes = Object.freeze([
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/mp4;codecs=avc1.42E01E",
      "video/webm",
      "video/mp4",
    ]);
    /** @type {RollingConfig} */
    #config = {
      target: null,
      window: 5000,
      segmentDuration: 250,
      quality: "high",
      fps: null,
      videoBitsPerSecond: null,
      audioBitsPerSecond: null,
      audio: false,
      mimeTypes: RollingCapture.mimeTypes,
      transferChunkSize: 262144,
      eventPrefix: "evidence",
      maxBufferBytes: 64 * 1024 * 1024,
      maxCompletedBytes: 256 * 1024 * 1024,
      maxCaptures: 32,
      autoRemoveAfterTransfer: true,
    };
    /** @type {?Element} */
    #target = null;
    /** @type {?string} */
    #targetReference = null;
    /** @type {?MediaStream} */
    #stream = null;
    /** @type {?RollingSegment} */
    #current = null;
    /** @type {RollingSegmentResult[]} */
    #segments = [];
    #armed = false;
    /** @type {number|ReturnType<typeof setTimeout>} */
    #rotationTimer = 0;
    /** @type {Promise<unknown>} */
    #rotation = Promise.resolve();
    /** @type {Map<string, RollingCaptureTask>} */
    #captures = new Map();
    /** @type {Map<string, RollingVideoResult>} */
    #results = new Map();
    /** @type {Map<string, RollingImageResult>} */
    #images = new Map();
    /** @type {?string} */
    #lastCaptureId = null;
    /** @type {?string} */
    #mimeType = null;
    /**
     * @param {RollingOptions} [options] Initial recorder configuration.
     */
    constructor(options = {}) {
      super();
      this.set(options);
    }
    /**
     * @param {RollingOptions} [options] Initial recorder configuration.
     * @returns {Promise<RollingCapture>} Armed recorder instance.
     */
    static create = async (options = {}) => {
      const capture = new RollingCapture(options);
      await capture.arm();
      return capture;
    };
    /**
     * Return the current armed state.
     * @returns {SceneValue} The resulting value.
     */
    get armed() {
      return this.#armed;
    }
    /**
     * Return the current target state.
     * @returns {SceneValue} The resulting value.
     */
    get target() {
      return this.#target;
    }
    /**
     * Return the current quality state.
     *
     * @returns {RollingQuality} Effective encoder quality settings.
     */
    get quality() {
      const quality = this.#config.quality;
      const presets = /** @type {Readonly<Record<string, RollingQuality>>} */ (
        RollingCapture.qualities
      );
      const preset =
        typeof quality === "string"
          ? presets[quality]
          : presets[String("high")];
      return /** @type {RollingQuality} */ ({
        ...preset,
        ...(typeof quality === "object" ? quality : {}),
        ...(this.#config.fps == null
          ? {}
          : {
              fps: this.#config.fps,
            }),
        ...(this.#config.videoBitsPerSecond == null
          ? {}
          : {
              videoBitsPerSecond: this.#config.videoBitsPerSecond,
            }),
      });
    }
    /**
     * Return the current buffer state.
     * @returns {SceneValue} The resulting value.
     */
    get buffer() {
      const now = this.#now();
      const oldest = this.#segments[0]?.start ?? this.#current?.start ?? now;
      return {
        armed: this.#armed,
        segments: this.#segments.length,
        bytes: this.#segments.reduce(
          (sum, segment) => sum + segment.blob.size,
          0,
        ),
        duration: Math.max(0, now - oldest),
        configuredDuration: this.#config.window,
        maxBytes: this.#config.maxBufferBytes,
        oldest,
        now,
      };
    }
    /**
     * Handle config for scene-evidence processing.
     *
     * @returns {RollingConfig} Resolved recorder configuration snapshot.
     */
    config() {
      return {
        ...this.#config,
        target: this.#targetReference,
        quality:
          typeof this.#config.quality === "object"
            ? {
                ...this.#config.quality,
              }
            : this.#config.quality,
        mimeTypes: [...this.#config.mimeTypes],
      };
    }
    /**
     * Merge new options into the recorder configuration.
     * @param {RollingOptions} [options] Configuration overrides.
     * @returns {RollingCapture} This recorder for chaining.
     * @throws {Error} When the operation cannot complete.
     */
    set(options = {}) {
      if (this.#armed)
        throw new Error("Disarm before changing recorder configuration.");
      const { target, ...configuration } = options;
      this.#config = {
        ...this.#config,
        ...configuration,
      };
      if (target !== undefined) this.setTarget(target);
      this.#validate();
      this.#emit("configchange", {
        config: this.config(),
      });
      return this;
    }
    /**
     * Set the element or selector that supplies the video stream.
     * @param {string|Element} target Selector or element to record.
     * @returns {RollingCapture} This recorder for chaining.
     * @throws {Error} When the operation cannot complete.
     * @throws {TypeError} When the operation cannot complete.
     */
    setTarget(target) {
      if (this.#armed) throw new Error("Target cannot change while armed.");
      const element = this.#resolveTarget(target);
      const surface = /** @type {Element & RollingCaptureSurface} */ (element);
      if (
        typeof surface.captureStream !== "function" &&
        typeof surface.webkitCaptureStream !== "function"
      )
        throw new TypeError(
          "Video target must expose captureStream(), normally canvas or video.",
        );
      this.#target = element;
      this.#targetReference = typeof target === "string" ? target : null;
      this.#emit("targetchange", {
        target: this.#describeTarget(),
      });
      return this;
    }
    /**
     * Subscribe to an event and return an unsubscribe function.
     * @param {string} type Event name.
     * @param {EventListenerOrEventListenerObject} callback Event handler.
     * @param {boolean|AddEventListenerOptions} [options] Listener options.
     * @returns {() => void} Unsubscribe function.
     */
    on(type, callback, options) {
      this.addEventListener(type, callback, options);
      return () => this.removeEventListener(type, callback, options);
    }
    /**
     * Handle arm for scene-evidence processing.
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} If the capture target or MediaRecorder is unavailable.
     */
    async arm() {
      if (this.#armed) return this.status();
      if (!this.#target) throw new Error("No video target configured.");
      if (typeof MediaRecorder === "undefined")
        throw new Error("MediaRecorder is unavailable in this browser.");
      this.#mimeType =
        this.#config.mimeTypes.find(type =>
          MediaRecorder.isTypeSupported(type),
        ) ?? null;
      this.#stream = this.#captureStream();
      this.#segments = [];
      this.#armed = true;
      const current = this.#createSegment();
      this.#current = current;
      current.recorder.start();
      current.start = this.#now();
      this.#scheduleRotation();
      this.#emit("armed", this.status());
      return this.status();
    }
    /**
     * Handle disarm for scene-evidence processing.
     *
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    async disarm(
      /** @type {RollingDisarmOptions} */ { clear = false, force = false } = {},
    ) {
      if (!this.#armed) return this.status();
      if (this.#captures.size && !force)
        throw new Error("Active captures exist; stop them or use force=true.");
      if (force)
        await Promise.all(
          [...this.#captures.keys()].map(id =>
            this.stop(id, {
              reason: "disarm",
            }),
          ),
        );
      this.#armed = false;
      clearTimeout(this.#rotationTimer);
      await this.#rotation.catch(() => null);
      const current = this.#current;
      if (current && current.recorder.state !== "inactive") {
        current.recorder.stop();
        await current.done;
      }
      this.#stream?.getTracks().forEach(track => {
        track.stop();
      });
      this.#stream = null;
      this.#current = null;
      if (clear) this.#segments = [];
      this.#emit("disarmed", this.status());
      return this.status();
    }
    /**
     * Handle start for scene-evidence processing.
     *
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     * @throws {RangeError} When the operation cannot complete.
     */
    async start(
      /** @type {RollingStartOptions} */ {
        before = 0,
        duration = 0,
        id = evidenceId(),
        metadata = null,
      } = {},
    ) {
      if (!this.#armed) await this.arm();
      if (before < 0 || duration < 0)
        throw new RangeError("before and duration must be >= 0.");
      if (before > this.#config.window)
        throw new RangeError(
          `before ${before} exceeds window ${this.#config.window}.`,
        );
      if (this.#captures.has(id))
        throw new Error(`Capture ${id} already exists.`);
      const trigger = this.#now();
      /** @type {(value: unknown) => void} */
      let resolve = () => {};
      /** @type {(reason?: unknown) => void} */
      let reject = () => {};
      const done = new Promise((accept, fail) => {
        resolve = accept;
        reject = fail;
      });
      /** @type {RollingCaptureTask} */
      const capture = {
        id,
        kind: "video",
        trigger,
        requestedStart: trigger - before,
        requestedEnd: null,
        before,
        duration,
        metadata,
        timer: 0,
        stopping: false,
        done,
        resolve,
        reject,
      };
      this.#captures.set(id, capture);
      this.#lastCaptureId = id;
      await this.#rotate();
      if (duration > 0) {
        const end = trigger + duration;
        capture.timer = setTimeout(
          () => {
            this.stop(id, {
              reason: "duration",
              at: end,
            }).catch(() => null);
          },
          Math.max(0, end - this.#now()),
        );
      }
      const result = {
        id,
        kind: "video",
        trigger,
        requestedStart: capture.requestedStart,
        before,
        duration,
        metadata,
      };
      this.#emit("start", result);
      return result;
    }
    /**
     * Handle stop for scene-evidence processing.
     *
     * @param {string|null} [id] @param {RollingStopOptions} [options]
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async stop(
      id = this.#lastCaptureId,
      { reason = "manual", at = null } = {},
    ) {
      if (id === null) return null;
      const capture = this.#captures.get(id);
      if (!capture) {
        const completed = this.#results.get(id);
        return completed ? this.#publicVideo(completed) : null;
      }
      if (capture.stopping) return capture.done;
      capture.stopping = true;
      clearTimeout(capture.timer);
      capture.requestedEnd = at ?? this.#now();
      try {
        await this.#rotate();
        const result = this.#finishCapture(capture, reason);
        this.#captures.delete(id);
        this.#results.delete(id);
        this.#results.set(id, result);
        this.#pruneCompleted();
        const publicResult = this.#publicVideo(result);
        capture.resolve(publicResult);
        this.#emit("stop", publicResult);
        this.#emit("result", publicResult);
        this.#prune();
        return publicResult;
      } catch (error) {
        this.#captures.delete(id);
        capture.reject(error);
        this.#emit("error", {
          id,
          name: error instanceof Error ? error.name : "Error",
          message: error instanceof Error ? error.message : String(error),
        });
        throw error;
      }
    }
    /**
     * Handle record for scene-evidence processing.
     *
     * @param {RollingStartOptions} [options]
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    async record(options = {}) {
      if (!(typeof options.duration === "number" && options.duration > 0))
        throw new Error(
          "record() requires duration > 0; use start()/stop() otherwise.",
        );
      const { id } = await this.start(options);
      return this.done(id);
    }
    /**
     * Handle done for scene-evidence processing.
     *
     * @param {string|null} [id]
     * @returns {SceneValue} The resulting value.
     */
    done(id = this.#lastCaptureId) {
      if (id === null)
        return Promise.reject(new Error("No capture is active."));
      const result = this.#results.get(id);
      if (result) return Promise.resolve(this.#publicVideo(result));
      const capture = this.#captures.get(id);
      if (!capture) return Promise.reject(new Error(`Unknown capture ${id}.`));
      return capture.done;
    }
    /**
     * Handle snapshot for scene-evidence processing.
     *
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {RangeError} When the operation cannot complete.
     */
    async snapshot(
      /** @type {RollingSnapshotOptions} */ {
        target = this.#target,
        type = "image/png",
        quality = 0.95,
        scale = 1,
        id = evidenceId(),
        metadata = null,
        background = "transparent",
      } = {},
    ) {
      const source = this.#resolveTarget(target);
      if (!(scale > 0)) throw new RangeError("scale must be > 0.");
      const blob = await this.#snapshotBlob(source, {
        type,
        quality,
        scale,
        background,
      });
      const dimensions = await this.#blobDimensions(blob);
      const result = {
        id,
        kind: "capture",
        createdAt: this.#now(),
        width: dimensions.width,
        height: dimensions.height,
        mimeType: blob.type || type,
        size: blob.size,
        quality,
        scale,
        metadata,
        blob,
      };
      this.#images.delete(id);
      this.#images.set(id, result);
      this.#pruneCompleted();
      const publicResult = this.#publicImage(result);
      this.#emit("capture", publicResult);
      this.#emit("snapshot", publicResult);
      this.#emit("result", publicResult);
      return publicResult;
    }
    /**
     * Handle transfer for scene-evidence processing.
     *
     * @param {string} id @param {RollingTransferOptions} [options]
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     * @throws {RangeError} When the operation cannot complete.
     */
    async transfer(
      id,
      {
        sink = "__evidenceSink",
        chunkSize = this.#config.transferChunkSize,
      } = {},
    ) {
      const send = evidenceGlobal[sink];
      if (typeof send !== "function")
        throw new Error(`Sink ${sink} is not exposed.`);
      const sinkFn = /** @type {EvidenceSink} */ (
        /** @type {unknown} */ (send)
      );
      if (!(chunkSize > 0)) throw new RangeError("chunkSize must be > 0.");
      const video = this.#results.get(id);
      const image = this.#images.get(id);
      if (!video && !image) throw new Error(`No completed capture ${id}.`);
      const transferId = evidenceId();
      const metadata = video
        ? this.#publicVideo(video)
        : this.#publicImage(/** @type {RollingImageResult} */ (image));
      /** @type {{blob:Blob,asset:string,start?:number,end?:number}[]} */
      const assets = video
        ? video.segments.map((segment, index) => ({
            blob: segment.blob,
            asset: `segment-${String(index).padStart(4, "0")}.${this.#extension(segment.mimeType)}`,
            start: segment.start,
            end: segment.end,
          }))
        : [
            {
              blob: /** @type {RollingImageResult} */ (image).blob,
              asset: `capture.${this.#imageExtension(/** @type {RollingImageResult} */ (image).mimeType)}`,
            },
          ];
      await sinkFn({
        event: "transfer-start",
        transferId,
        id,
        kind: metadata.kind,
        metadata,
        assetCount: assets.length,
      });
      this.#emit("transferstart", {
        transferId,
        id,
        kind: metadata.kind,
      });
      await Promise.all(
        assets.map((asset, index) =>
          this.#transferBlob(
            sinkFn,
            asset.blob,
            {
              transferId,
              id,
              asset: asset.asset,
              assetIndex: index,
              assetCount: assets.length,
              mimeType: asset.blob.type || "application/octet-stream",
              start: asset.start ?? null,
              end: asset.end ?? null,
            },
            chunkSize,
          ),
        ),
      );
      await sinkFn({
        event: "transfer-end",
        transferId,
        id,
        assetCount: assets.length,
      });
      this.#emit("transferend", {
        transferId,
        id,
        kind: metadata.kind,
      });
      if (this.#config.autoRemoveAfterTransfer) this.remove(id);
      return {
        transferId,
        ...metadata,
      };
    }
    /**
     * Handle remove for scene-evidence processing.
     *
     * @param {string} id
     * @returns {SceneValue} The resulting value.
     */
    remove(id) {
      const videoRemoved = this.#results.delete(id);
      const imageRemoved = this.#images.delete(id);
      return videoRemoved || imageRemoved;
    }
    /**
     * Handle clear for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     * @throws {Error} If captures are still active.
     */
    clear() {
      if (this.#captures.size)
        throw new Error("Cannot clear with active captures.");
      this.#results.clear();
      this.#images.clear();
      this.#segments = [];
      return this;
    }
    /**
     * Handle status for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    status() {
      return {
        armed: this.#armed,
        target: this.#describeTarget(),
        quality: this.quality,
        mimeType: this.#mimeType,
        buffer: this.buffer,
        activeCaptures: [...this.#captures.keys()],
        completedCaptures: [...this.#results.keys()],
        captures: [...this.#images.keys()],
        memory: {
          bufferBytes: this.#segments.reduce(
            (sum, segment) => sum + segment.blob.size,
            0,
          ),
          completedBytes: this.#completedBytes(),
          maxBufferBytes: this.#config.maxBufferBytes,
          maxCompletedBytes: this.#config.maxCompletedBytes,
          maxCaptures: this.#config.maxCaptures,
        },
      };
    }
    /**
     * Handle #finish Capture for scene-evidence processing.
     *
     * @param {RollingCaptureTask} capture
     * @param {string} reason
     * @returns {SceneValue} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    #finishCapture(capture, reason) {
      const requestedStart = capture.requestedStart;
      const requestedEnd = capture.requestedEnd;
      if (requestedEnd === null)
        throw new Error("Capture has no requested end time.");
      const segments = this.#segments.filter(
        segment =>
          segment.end > requestedStart && segment.start < requestedEnd,
      );
      if (!segments.length)
        throw new Error("No buffered video intersects the requested interval.");
      const firstSegment = segments[0];
      const lastSegment = segments.at(-1);
      if (!firstSegment || !lastSegment)
        throw new Error("Capture segments are unavailable.");
      const sourceStart = firstSegment.start;
      const sourceEnd = lastSegment.end;
      const actualStart = Math.max(requestedStart, sourceStart);
      const actualEnd = Math.min(requestedEnd, sourceEnd);
      return {
        id: capture.id,
        kind: "video",
        trigger: capture.trigger,
        requestedStart,
        requestedEnd,
        actualStart,
        actualEnd,
        requestedBefore: capture.before,
        actualBefore: Math.max(0, capture.trigger - actualStart),
        missingBefore: Math.max(0, actualStart - requestedStart),
        sourceStart,
        sourceEnd,
        trimStart: actualStart - sourceStart,
        trimDuration: Math.max(0, actualEnd - actualStart),
        reason,
        metadata: capture.metadata,
        mimeType: firstSegment.mimeType,
        audio: this.#config.audio,
        size: segments.reduce((sum, segment) => sum + segment.blob.size, 0),
        segments,
      };
    }
    /**
     * Handle #rotate for scene-evidence processing.
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async #rotate() {
      if (!this.#armed) return null;
      this.#rotation = this.#rotation
        .catch(() => null)
        .then(() => this.#rotateNow());
      return this.#rotation;
    }
    /**
     * Handle #rotate Now for scene-evidence processing.
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async #rotateNow() {
      if (!this.#armed || !this.#current) return null;
      clearTimeout(this.#rotationTimer);
      const previous = this.#current;
      const next = this.#createSegment();
      next.recorder.start();
      next.start = this.#now();
      this.#current = next;
      if (previous.recorder.state !== "inactive") previous.recorder.stop();
      const result = await previous.done;
      this.#prune();
      this.#scheduleRotation();
      return result;
    }
    /**
     * Handle #create Segment for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     * @throws {Error} If the capture stream is unavailable.
     */
    #createSegment() {
      /** @type {Blob[]} */
      const chunks = [];
      /** @type {(value: RollingSegmentResult) => void} */
      let resolve = () => {};
      /** @type {(reason?: unknown) => void} */
      let reject = () => {};
      const done = new Promise((accept, fail) => {
        resolve = accept;
        reject = fail;
      });
      const { videoBitsPerSecond } = this.quality;
      if (!this.#stream) throw new Error("Capture stream is unavailable.");
      const recorder = new MediaRecorder(this.#stream, {
        ...(this.#mimeType
          ? {
              mimeType: this.#mimeType,
            }
          : {}),
        ...(videoBitsPerSecond
          ? {
              videoBitsPerSecond,
            }
          : {}),
        ...(this.#config.audioBitsPerSecond
          ? {
              audioBitsPerSecond: this.#config.audioBitsPerSecond,
            }
          : {}),
      });
      const segment = {
        recorder,
        chunks,
        start: 0,
        done,
      };
      recorder.addEventListener("dataavailable", event => {
        if (event.data.size) chunks.push(event.data);
      });
      recorder.addEventListener(
        "error",
        event =>
          reject(event.error ?? new Error("MediaRecorder segment failed.")),
        {
          once: true,
        },
      );
      recorder.addEventListener(
        "stop",
        async () => {
          const end = this.#now();
          const mimeType =
            recorder.mimeType ||
            this.#mimeType ||
            chunks[0]?.type ||
            "video/webm";
          const blob = new Blob(chunks, {
            type: mimeType,
          });
          const result = {
            start: segment.start,
            end,
            duration: end - segment.start,
            mimeType,
            blob,
          };
          if (blob.size && await this.#validMediaBlob(blob, mimeType)) {
            this.#segments.push(result);
            this.#emit("segment", this.#publicSegment(result));
            this.#emit("buffer", this.buffer);
          } else if (blob.size)
            this.#emit("segmentdiscarded", {
              start: segment.start,
              end,
              duration: end - segment.start,
              mimeType,
              size: blob.size,
              reason: "invalid-or-header-only-media-container",
            });
          resolve(result);
        },
        {
          once: true,
        },
      );
      return segment;
    }
    /**
     * Handle #valid Media Blob for scene-evidence processing.
     *
     * @param {Blob} blob
     * @param {string} mimeType
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async #validMediaBlob(blob, mimeType) {
      if (blob.size < 256) return false;
      const bytes = new Uint8Array(await blob.slice(0, 16).arrayBuffer());
      if (mimeType.includes("webm"))
        return (
          bytes.length >= 4 &&
          bytes[0] === 0x1a &&
          bytes[1] === 0x45 &&
          bytes[2] === 0xdf &&
          bytes[3] === 0xa3
        );
      if (mimeType.includes("mp4"))
        return (
          bytes.length >= 8 &&
          String.fromCharCode(...bytes.slice(4, 8)) === "ftyp"
        );
      return true;
    }
    /**
     * Handle #schedule Rotation for scene-evidence processing.
     */
    #scheduleRotation() {
      clearTimeout(this.#rotationTimer);
      if (this.#armed)
        this.#rotationTimer = setTimeout(() => {
          this.#rotate().catch(() => null);
        }, this.#config.segmentDuration);
    }
    /**
     * Handle #prune for scene-evidence processing.
     */
    #prune() {
      const now = this.#now();
      let floor = now - this.#config.window - this.#config.segmentDuration * 2;
      for (const capture of this.#captures.values())
        floor = Math.min(floor, capture.requestedStart);
      while ((this.#segments[0]?.end ?? Infinity) < floor)
        this.#segments.shift();
      let bytes = this.#segments.reduce(
        (sum, segment) => sum + segment.blob.size,
        0,
      );
      const protectedStart = this.#captures.size
        ? Math.min(
            ...[...this.#captures.values()].map(
              capture => capture.requestedStart,
            ),
          )
        : Infinity;
      while (
        this.#segments.length > 1 &&
        bytes > this.#config.maxBufferBytes &&
        (this.#segments[0]?.end ?? Infinity) < protectedStart
      ) {
        const removed = this.#segments.shift();
        if (removed) bytes -= removed.blob.size;
      }
    }
    /**
     * Handle #prune Completed for scene-evidence processing.
     */
    #pruneCompleted() {
      while (
        this.#results.size + this.#images.size > this.#config.maxCaptures ||
        this.#completedBytes() > this.#config.maxCompletedBytes
      ) {
        const video = this.#results.entries().next().value;
        const image = this.#images.entries().next().value;
        if (!video && !image) break;
        const videoTime = video?.[1]?.requestedEnd ?? Infinity;
        const imageTime = image?.[1]?.createdAt ?? Infinity;
        if (videoTime <= imageTime && video) this.#results.delete(video[0]);
        else if (image) this.#images.delete(image[0]);
      }
    }
    /**
     * Handle #completed Bytes for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    #completedBytes() {
      return (
        [...this.#results.values()].reduce(
          (sum, value) => sum + value.size,
          0,
        ) +
        [...this.#images.values()].reduce((sum, value) => sum + value.size, 0)
      );
    }
    /**
     * Handle #capture Stream for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     * @throws {Error} If the capture target or capture stream is unavailable.
     */
    #captureStream() {
      if (!this.#target) throw new Error("Capture target is unavailable.");
      const surface = /** @type {RollingCaptureSurface} */ (this.#target);
      const capture = surface.captureStream ?? surface.webkitCaptureStream;
      if (!capture)
        throw new Error("Capture target does not expose captureStream().");
      const stream = capture.call(surface, this.quality.fps);
      if (!this.#config.audio)
        stream.getAudioTracks().forEach(track => {
          stream.removeTrack(track);
          track.stop();
        });
      return stream;
    }
    /**
     * Handle #snapshot Blob for scene-evidence processing.
     *
     * @param {Element} source @param {RollingDrawOptions} options
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async #snapshotBlob(source, { type, quality, scale, background }) {
      if (
        source instanceof HTMLCanvasElement ||
        source instanceof HTMLVideoElement ||
        source instanceof HTMLImageElement
      ) {
        const { width, height } = this.#sourceSize(source);
        return this.#drawToBlob(source, width, height, {
          type,
          quality,
          scale,
          background,
        });
      }
      if (source instanceof SVGSVGElement) {
        const rect = source.getBoundingClientRect();
        const markup = new XMLSerializer().serializeToString(source);
        const blob = new Blob([markup], {
          type: "image/svg+xml",
        });
        const image = await this.#loadImage(URL.createObjectURL(blob), true);
        return this.#drawToBlob(image, rect.width, rect.height, {
          type,
          quality,
          scale,
          background,
        });
      }
      if (evidenceGlobal.htmlToImage?.toCanvas) {
        const data = await Descriptor.captureElementDataUrl(source, {
          mime: type,
          quality,
          pixelRatio: scale,
          background,
          fresh: true,
        });
        return fetch(data).then(response => response.blob());
      }
      return this.#domElementBlob(source, {
        type,
        quality,
        scale,
        background,
      });
    }
    /**
     * Handle #dom Element Blob for scene-evidence processing.
     *
     * @param {Element} source @param {RollingDrawOptions} options
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    async #domElementBlob(source, { type, quality, scale, background }) {
      const rootRect = source.getBoundingClientRect();
      if (!(rootRect.width > 0 && rootRect.height > 0))
        throw new Error("Capture target has no rendered area.");
      const canvas = Object.assign(document.createElement("canvas"), {
        width: Math.max(1, Math.round(rootRect.width * scale)),
        height: Math.max(1, Math.round(rootRect.height * scale)),
      });
      const context = canvas.getContext("2d");
      if (!context) throw new Error("2D canvas context unavailable.");
      context.scale(scale, scale);
      if (background !== "transparent") {
        context.fillStyle = background;
        context.fillRect(0, 0, rootRect.width, rootRect.height);
      }
      const nodes = [source, ...source.querySelectorAll("*")];
      /** @param {number} index @returns {Promise<void>} */
      const drawNode = async index => {
        const element = nodes[index];
        if (!element) return;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          Number(style.opacity) <= 0 ||
          rect.width <= 0 ||
          rect.height <= 0 ||
          rect.right <= rootRect.left ||
          rect.left >= rootRect.right ||
          rect.bottom <= rootRect.top ||
          rect.top >= rootRect.bottom
        ) {
          await drawNode(index + 1);
          return;
        }
        const x = rect.left - rootRect.left;
        const y = rect.top - rootRect.top;
        context.save();
        context.globalAlpha = this.#effectiveOpacity(element, source);
        this.#clipToAncestors(context, element, source, rootRect);
        this.#drawElementBox(
          context,
          element,
          style,
          x,
          y,
          rect.width,
          rect.height,
        );
        if (
          element instanceof HTMLCanvasElement ||
          element instanceof HTMLImageElement ||
          element instanceof HTMLVideoElement
        )
          try {
            context.drawImage(element, x, y, rect.width, rect.height);
          } catch {
            // Media may be unavailable or cross-origin; retain the box evidence.
          }
        else if (element instanceof SVGSVGElement)
          try {
            const markup = new XMLSerializer().serializeToString(element);
            const url = URL.createObjectURL(
              new Blob([markup], {
                type: "image/svg+xml",
              }),
            );
            const image = await this.#loadImage(url, true);
            context.drawImage(image, x, y, rect.width, rect.height);
          } catch {
            // SVG external resources can prevent rasterization; retain its box.
          }
        this.#drawDirectText(context, element, style, rootRect);
        context.restore();
        await drawNode(index + 1);
      };
      await drawNode(0);
      return new Promise((resolve, reject) => {
        try {
          canvas.toBlob(
            blob =>
              blob
                ? resolve(blob)
                : reject(new Error("Image encoding failed.")),
            type,
            quality,
          );
        } catch (error) {
          reject(error);
        }
      });
    }
    /**
     * Handle #draw Element Box for scene-evidence processing.
     *
     * @param {CanvasRenderingContext2D} context
     * @param {Element} element
     * @param {CSSStyleDeclaration} style
     * @param {number} x
     * @param {number} y
     * @param {number} width
     * @param {number} height
     */
    #drawElementBox(context, element, style, x, y, width, height) {
      const background = style.backgroundColor;
      const radius = Math.max(0, parseFloat(style.borderTopLeftRadius) || 0);
      const path = () => {
        context.beginPath();
        if (radius && typeof context.roundRect === "function")
          context.roundRect(
            x,
            y,
            width,
            height,
            Math.min(radius, width / 2, height / 2),
          );
        else context.rect(x, y, width, height);
      };
      if (
        background &&
        background !== "transparent" &&
        !background.endsWith(", 0)")
      ) {
        path();
        context.fillStyle = background;
        context.fill();
      }
      /** @type {[string,string,string,string][]} */
      const sides = [
        [
          "top",
          style.borderTopWidth,
          style.borderTopStyle,
          style.borderTopColor,
        ],
        [
          "right",
          style.borderRightWidth,
          style.borderRightStyle,
          style.borderRightColor,
        ],
        [
          "bottom",
          style.borderBottomWidth,
          style.borderBottomStyle,
          style.borderBottomColor,
        ],
        [
          "left",
          style.borderLeftWidth,
          style.borderLeftStyle,
          style.borderLeftColor,
        ],
      ];
      for (const [side, widthValue, lineStyle, color] of sides) {
        const lineWidth = parseFloat(widthValue);
        if (!(lineWidth > 0) || lineStyle === "none" || lineStyle === "hidden")
          continue;
        context.beginPath();
        context.lineWidth = lineWidth;
        context.strokeStyle = color;
        context.setLineDash(
          lineStyle === "dashed"
            ? [lineWidth * 3, lineWidth * 2]
            : lineStyle === "dotted"
              ? [lineWidth, lineWidth]
              : [],
        );
        if (side === "top") {
          context.moveTo(x, y + lineWidth / 2);
          context.lineTo(x + width, y + lineWidth / 2);
        } else if (side === "right") {
          context.moveTo(x + width - lineWidth / 2, y);
          context.lineTo(x + width - lineWidth / 2, y + height);
        } else if (side === "bottom") {
          context.moveTo(x, y + height - lineWidth / 2);
          context.lineTo(x + width, y + height - lineWidth / 2);
        } else {
          context.moveTo(x + lineWidth / 2, y);
          context.lineTo(x + lineWidth / 2, y + height);
        }
        context.stroke();
      }
      context.setLineDash([]);
      if (element instanceof HTMLInputElement && element.value) {
        context.fillStyle = style.color;
        context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
        context.textBaseline = "middle";
        context.fillText(element.value, x + 4, y + height / 2);
      }
    }
    /**
     * Handle #draw Direct Text for scene-evidence processing.
     *
     * @param {CanvasRenderingContext2D} context
     * @param {Element} element
     * @param {CSSStyleDeclaration} style
     * @param {DOMRect} rootRect
     */
    #drawDirectText(context, element, style, rootRect) {
      const nodes = [...element.childNodes].filter(
        node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
      );
      if (!nodes.length) return;
      context.fillStyle = style.color;
      context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      context.textBaseline = "alphabetic";
      context.textAlign =
        style.textAlign === "center"
          ? "center"
          : style.textAlign === "right" || style.textAlign === "end"
            ? "right"
            : "left";
      for (const node of nodes) {
        const text = node.textContent ?? "";
        for (const match of text.matchAll(/\S+(?:\s+|$)/g)) {
          const range = document.createRange();
          range.setStart(node, match.index);
          range.setEnd(
            node,
            Math.min(text.length, match.index + match[0].length),
          );
          const rectangles = [...range.getClientRects()];
          for (const rect of rectangles) {
            const value = match[0].trim();
            if (!value || rect.width <= 0 || rect.height <= 0) continue;
            const x =
              context.textAlign === "center"
                ? rect.left - rootRect.left + rect.width / 2
                : context.textAlign === "right"
                  ? rect.right - rootRect.left
                  : rect.left - rootRect.left;
            context.fillText(
              value,
              x,
              rect.bottom - rootRect.top - Math.max(0, rect.height * 0.12),
            );
          }
        }
      }
    }
    /**
     * Handle #effective Opacity for scene-evidence processing.
     *
     * @param {Element} element
     * @param {Element} root
     * @returns {SceneValue} The resulting value.
     */
    #effectiveOpacity(element, root) {
      let opacity = 1;
      for (
        let current = /** @type {Element|null} */ (element);
        current instanceof Element;
        current = current.parentElement
      ) {
        opacity *= Number(getComputedStyle(current).opacity) || 0;
        if (current === root) break;
      }
      return Math.max(0, Math.min(1, opacity));
    }
    /**
     * Handle #clip To Ancestors for scene-evidence processing.
     *
     * @param {CanvasRenderingContext2D} context
     * @param {Element} element
     * @param {Element} root
     * @param {DOMRect} rootRect
     */
    #clipToAncestors(context, element, root, rootRect) {
      for (
        let current = /** @type {Element|null} */ (element);
        current instanceof Element;
        current = current.parentElement
      ) {
        const style = getComputedStyle(current);
        if (
          [style.overflow, style.overflowX, style.overflowY].some(value =>
            ["hidden", "clip", "scroll", "auto"].includes(value),
          ) ||
          current === root
        ) {
          const rect = current.getBoundingClientRect();
          context.beginPath();
          context.rect(
            Math.max(0, rect.left - rootRect.left),
            Math.max(0, rect.top - rootRect.top),
            Math.max(
              0,
              Math.min(rootRect.right, rect.right) -
                Math.max(rootRect.left, rect.left),
            ),
            Math.max(
              0,
              Math.min(rootRect.bottom, rect.bottom) -
                Math.max(rootRect.top, rect.top),
            ),
          );
          context.clip();
        }
        if (current === root) break;
      }
    }
    /**
     * Handle #draw To Blob for scene-evidence processing.
     *
     * @param {CanvasImageSource} source
     * @param {number} width
     * @param {number} height
     * @param {RollingDrawOptions} options
     * @returns {SceneValue} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    #drawToBlob(source, width, height, options) {
      const { type, quality, scale, background } = options;
      const canvas = Object.assign(document.createElement("canvas"), {
        width: Math.max(1, Math.round(width * scale)),
        height: Math.max(1, Math.round(height * scale)),
      });
      const context = canvas.getContext("2d");
      if (!context) throw new Error("2D canvas context unavailable.");
      const resolvedBackground =
        background === "transparent" ? null : background;
      if (resolvedBackground) {
        context.fillStyle = resolvedBackground;
        context.fillRect(0, 0, canvas.width, canvas.height);
      }
      context.drawImage(source, 0, 0, canvas.width, canvas.height);
      return new Promise((resolve, reject) => {
        canvas.toBlob(
          blob =>
            blob ? resolve(blob) : reject(new Error("Image encoding failed.")),
          type,
          quality,
        );
      });
    }
    /**
     * Handle #load Image for scene-evidence processing.
     *
     * @param {string} url
     * @param {boolean} [revoke]
     * @returns {SceneValue} The resulting value.
     */
    #loadImage(url, revoke = false) {
      return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => {
          if (revoke) URL.revokeObjectURL(url);
          resolve(image);
        };
        image.onerror = error => {
          if (revoke) URL.revokeObjectURL(url);
          reject(error);
        };
        image.src = url;
      });
    }
    /**
     * Handle #blob Dimensions for scene-evidence processing.
     *
     * @param {Blob} blob
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async #blobDimensions(blob) {
      const url = URL.createObjectURL(blob);
      const image = await this.#loadImage(url, true);
      return {
        width: image.naturalWidth,
        height: image.naturalHeight,
      };
    }
    /**
     * Handle #source Size for scene-evidence processing.
     *
     * @param {CanvasImageSource} source
     * @returns {SceneValue} The resulting value.
     */
    #sourceSize(source) {
      if (source instanceof HTMLVideoElement)
        return {
          width: source.videoWidth,
          height: source.videoHeight,
        };
      if (source instanceof HTMLImageElement)
        return {
          width: source.naturalWidth,
          height: source.naturalHeight,
        };
      if ("width" in source && "height" in source)
        return {
          width: Number(source.width),
          height: Number(source.height),
        };
      return {
        width: 0,
        height: 0,
      };
    }
    /**
     * Handle #transfer Blob for scene-evidence processing.
     *
     * @param {EvidenceSink} send
     * @param {Blob} blob
     * @param {Record<string, unknown>} metadata
     * @param {number} chunkSize
     */
    async #transferBlob(send, blob, metadata, chunkSize) {
      const sha256 = await this.#sha256(blob);
      const chunks = Math.ceil(blob.size / chunkSize);
      await send({
        event: "asset-start",
        ...metadata,
        size: blob.size,
        chunks,
        sha256,
      });
      /** @param {number} index @returns {Promise<void>} */
      const sendChunk = async index => {
        if (index >= chunks) return;
        const part = blob.slice(
          index * chunkSize,
          Math.min(blob.size, (index + 1) * chunkSize),
        );
        await send({
          event: "chunk",
          ...metadata,
          index,
          chunks,
          sha256,
          data: await this.#base64(part),
        });
        this.#emit("transferprogress", {
          id: metadata[String("id")],
          asset: metadata[String("asset")],
          index: index + 1,
          chunks,
          progress: (index + 1) / chunks,
        });
        await sendChunk(index + 1);
      };
      await sendChunk(0);
      await send({
        event: "asset-end",
        ...metadata,
        size: blob.size,
        chunks,
        sha256,
      });
    }
    /** @param {Blob} blob */
    #sha256 = async blob => {
      const sha = evidenceGlobal.__evidenceSha256;
      if (typeof sha !== "function")
        throw new Error("SHA-256 helper is unavailable.");
      return [
        ...new Uint8Array(
          await /** @type {(buffer:ArrayBuffer)=>Promise<ArrayBuffer>} */ (
            /** @type {unknown} */ (sha)
          )(await blob.arrayBuffer()),
        ),
      ]
        .map(byte => byte.toString(16).padStart(2, "0"))
        .join("");
    };
    /**
     * Handle #base64 for scene-evidence processing.
     *
     * @param {Blob} blob
     * @returns {SceneValue} The resulting value.
     */
    #base64(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(reader.error);
        reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
        reader.readAsDataURL(blob);
      });
    }
    /**
     * Handle #resolve Target for scene-evidence processing.
     *
     * @param {string|Element|null} target
     * @returns {SceneValue} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    #resolveTarget(target) {
      const element =
        typeof target === "string" ? document.querySelector(target) : target;
      if (!(element instanceof Element))
        throw new Error(`Target not found: ${String(target)}`);
      return element;
    }
    /**
     * Handle #public Video for scene-evidence processing.
     *
     * @param {RollingVideoResult} result
     * @returns {SceneValue} The resulting value.
     */
    #publicVideo(result) {
      return {
        id: result.id,
        kind: "video",
        trigger: result.trigger,
        requestedStart: result.requestedStart,
        requestedEnd: result.requestedEnd,
        actualStart: result.actualStart,
        actualEnd: result.actualEnd,
        requestedBefore: result.requestedBefore,
        actualBefore: result.actualBefore,
        missingBefore: result.missingBefore,
        sourceStart: result.sourceStart,
        sourceEnd: result.sourceEnd,
        trimStart: result.trimStart,
        trimDuration: result.trimDuration,
        reason: result.reason,
        metadata: result.metadata,
        mimeType: result.mimeType,
        audio: result.audio,
        size: result.size,
        segments: result.segments.map(segment =>
          this.#publicSegment(segment),
        ),
      };
    }
    /**
     * Handle #public Image for scene-evidence processing.
     *
     * @param {RollingImageResult} result
     * @returns {SceneValue} The resulting value.
     */
    #publicImage(result) {
      return {
        id: result.id,
        kind: "capture",
        createdAt: result.createdAt,
        width: result.width,
        height: result.height,
        mimeType: result.mimeType,
        size: result.size,
        quality: result.quality,
        scale: result.scale,
        metadata: result.metadata,
      };
    }
    /**
     * Handle #public Segment for scene-evidence processing.
     *
     * @param {RollingSegmentResult} segment
     * @returns {SceneValue} The resulting value.
     */
    #publicSegment(segment) {
      return {
        start: segment.start,
        end: segment.end,
        duration: segment.duration,
        mimeType: segment.mimeType,
        size: segment.blob.size,
      };
    }
    /**
     * Handle #describe Target for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    #describeTarget() {
      if (!this.#target) return null;
      return {
        selector: this.#targetReference,
        tag: this.#target.tagName.toLowerCase(),
        id: this.#target.id || null,
        width:
          this.#target instanceof HTMLVideoElement
            ? this.#target.videoWidth
            : this.#target.clientWidth,
        height:
          this.#target instanceof HTMLVideoElement
            ? this.#target.videoHeight
            : this.#target.clientHeight,
      };
    }
    /**
     * Handle #validate for scene-evidence processing.
     * @throws {Error} If the configured quality is unknown.
     * @throws {RangeError} If a numeric capture limit is not positive.
     */
    #validate() {
      if (
        typeof this.#config.quality === "string" &&
        !RollingCapture.qualities[this.#config.quality]
      )
        throw new Error(`Unknown quality ${this.#config.quality}.`);
      for (const [name, value] of /** @type {[string, number][]} */ ([
        ["window", this.#config.window],
        ["segmentDuration", this.#config.segmentDuration],
        ["transferChunkSize", this.#config.transferChunkSize],
        ["maxBufferBytes", this.#config.maxBufferBytes],
        ["maxCompletedBytes", this.#config.maxCompletedBytes],
        ["maxCaptures", this.#config.maxCaptures],
      ]))
        if (!(value > 0)) throw new RangeError(`${name} must be > 0.`);
    }
    /**
     * Handle #extension for scene-evidence processing.
     * @param {string} type Type.
     * @returns {SceneValue} The resulting value.
     */
    #extension(type = "") {
      return type.includes("mp4") ? "mp4" : "webm";
    }
    /**
     * Handle #image Extension for scene-evidence processing.
     * @param {string} type Type.
     * @returns {SceneValue} The resulting value.
     */
    #imageExtension(type = "") {
      return type.includes("jpeg")
        ? "jpg"
        : type.includes("webp")
          ? "webp"
          : "png";
    }
    /**
     * Handle #now for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    #now() {
      return performance.timeOrigin + performance.now();
    }
    /**
     * Handle #emit for scene-evidence processing.
     *
     * @param {string} type
     * @param {unknown} [detail]
     * @returns {SceneValue} The resulting value.
     */
    #emit(type, detail = {}) {
      const data = {
        type,
        timestamp: new Date().toISOString(),
        ...(detail && typeof detail === "object"
          ? detail
          : {
              detail,
            }),
      };
      this.dispatchEvent(
        new CustomEvent(type, {
          detail: data,
        }),
      );
      globalThis.dispatchEvent?.(
        new CustomEvent(`${this.#config.eventPrefix}:${type}`, {
          detail: data,
        }),
      );
      return data;
    }
  }
  /**
   * Provide Evidence Runtime scene-evidence operations.
   */
  class EvidenceRuntime extends EventTarget {
    static modes = Object.freeze(["video", "capture", "description"]);
    static events = Object.freeze([
      "configchange",
      "targetchange",
      "armed",
      "disarmed",
      "start",
      "stop",
      "result",
      "capture",
      "snapshot",
      "description",
      "segment",
      "segmentdiscarded",
      "buffer",
      "transferstart",
      "transferprogress",
      "transferend",
      "mark",
      "diagnostic",
      "error",
    ]);
    /** @type {EvidenceConfig} */
    #config;
    /** @type {RollingCapture} */
    #video;
    /** @type {Map<string, DescriptionResult>} */
    #descriptions = new Map();
    /** @type {EvidenceTimelineEntry[]} */
    #markers = [];
    /** @type {EvidenceTimelineEntry[]} */
    #diagnostics = [];
    /** @type {Array<() => void>} */
    #diagnosticCleanup = [];
    /** @type {MutationObserver|null} */
    #mutationObserver = null;
    /** @type {PerformanceObserver[]} */
    #performanceObservers = [];
    /** @param {EvidenceOptions} [options] */
    constructor(options = {}) {
      super();
      this.#config = {
        target: options.target ?? null,
        diagnostics: options.diagnostics ?? true,
        maxTimelineEntries: options.maxTimelineEntries ?? 2000,
        maxDescriptions: options.maxDescriptions ?? 16,
        maxDescriptionBytes: options.maxDescriptionBytes ?? 128 * 1024 * 1024,
        eventPrefix: options.eventPrefix ?? "evidence",
        ...options,
      };
      this.#video = new RollingCapture(options);
      for (const type of [
        "configchange",
        "targetchange",
        "armed",
        "disarmed",
        "start",
        "stop",
        "result",
        "capture",
        "snapshot",
        "segment",
        "segmentdiscarded",
        "buffer",
        "transferstart",
        "transferprogress",
        "transferend",
        "error",
      ])
        this.#video.addEventListener(type, event =>
          this.#emit(type, event instanceof CustomEvent ? event.detail : null),
        );
      if (this.#config.diagnostics) this.startDiagnostics();
    }
    /** @param {EvidenceOptions} [options] */
    static create = async (options = {}) => {
      const runtime = new EvidenceRuntime(options);
      if (options.autoArm !== false && options.target) await runtime.arm();
      return runtime;
    };
    /**
     * Return the current armed state.
     * @returns {SceneValue} The resulting value.
     */
    get armed() {
      return this.#video.armed;
    }
    /**
     * Return the current target state.
     * @returns {SceneValue} The resulting value.
     */
    get target() {
      return this.#video.target;
    }
    /**
     * Return the current quality state.
     * @returns {SceneValue} The resulting value.
     */
    get quality() {
      return this.#video.quality;
    }
    /**
     * Return the current buffer state.
     * @returns {SceneValue} The resulting value.
     */
    get buffer() {
      return this.#video.buffer;
    }
    /**
     * Handle config for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    config() {
      return {
        ...this.#video.config(),
        diagnostics: this.#config.diagnostics,
        maxTimelineEntries: this.#config.maxTimelineEntries,
        maxDescriptions: this.#config.maxDescriptions,
        maxDescriptionBytes: this.#config.maxDescriptionBytes,
      };
    }
    /**
     * Handle status for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    status() {
      const videoStatus = this.#video.status();
      return {
        ...videoStatus,
        descriptions: [...this.#descriptions.keys()],
        markers: this.#markers.length,
        diagnostics: this.#diagnostics.length,
        modes: [...EvidenceRuntime.modes],
        memory: {
          ...videoStatus.memory,
          descriptionBytes: this.#descriptionBytes(),
          maxDescriptionBytes: this.#config.maxDescriptionBytes,
          maxDescriptions: this.#config.maxDescriptions,
        },
      };
    }
    /**
     * Handle arm for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    arm() {
      return this.#video.arm();
    }
    /**
     * Handle disarm for scene-evidence processing.
     *
     * @param {RollingDisarmOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    disarm(options = {}) {
      return this.#video.disarm(options);
    }
    /**
     * Handle start for scene-evidence processing.
     *
     * @param {RollingStartOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    start(options = {}) {
      return this.#video.start(options);
    }
    /**
     * Handle stop for scene-evidence processing.
     *
     * @param {string|null} [id]
     * @param {RollingStopOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    stop(id = null, options = {}) {
      return this.#video.stop(id, options);
    }
    /**
     * Handle record for scene-evidence processing.
     *
     * @param {RollingStartOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    record(options = {}) {
      return this.#video.record(options);
    }
    /**
     * Handle done for scene-evidence processing.
     *
     * @param {string|null} [id]
     * @returns {SceneValue} The resulting value.
     */
    done(id = null) {
      return this.#video.done(id);
    }
    /**
     * Handle capture for scene-evidence processing.
     *
     * @param {RollingSnapshotOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    capture(options = {}) {
      return this.#video.snapshot(options);
    }
    /**
     * Handle snapshot for scene-evidence processing.
     *
     * @param {RollingSnapshotOptions} [options]
     * @returns {SceneValue} The resulting value.
     */
    snapshot(options = {}) {
      return this.#video.snapshot(options);
    }
    /**
     * Handle description for scene-evidence processing.
     * @returns {Promise<SceneValue>} The resulting value.
     */
    async description({
      target = this.#config.target,
      id = evidenceId(),
      metadata = null,
      options = {},
      externalizeBinary = true,
    } = {}) {
      const element = this.#resolveTarget(target);
      const scene = await Descriptor.describe(element, options);
      const bundle = externalizeBinary
        ? await SceneBinaryBundle.create(scene)
        : {
            manifest: scene,
            files: new Map(),
          };
      const result = {
        id,
        kind: "description",
        createdAt: this.#now(),
        metadata,
        manifest: bundle.manifest,
        files: bundle.files,
        manifestBytes: new TextEncoder().encode(JSON.stringify(bundle.manifest))
          .length,
        binaryBytes: [...bundle.files.values()].reduce(
          (sum, blob) => sum + blob.size,
          0,
        ),
      };
      this.#descriptions.delete(id);
      this.#descriptions.set(id, result);
      while (
        this.#descriptions.size > this.#config.maxDescriptions ||
        this.#descriptionBytes() > this.#config.maxDescriptionBytes
      ) {
        const oldest = this.#descriptions.keys().next().value;
        if (oldest) this.#descriptions.delete(oldest);
      }
      const output = this.#publicDescription(result);
      this.#emit("description", output);
      this.#emit("result", output);
      return output;
    }
    /**
     * Handle describe for scene-evidence processing.
     *
     * @param {Parameters<EvidenceRuntime["description"]>[0]} [options]
     * @returns {SceneValue} The resulting value.
     */
    describe(options = {}) {
      return this.description(options);
    }
    /**
     * Handle evidence for scene-evidence processing.
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} If video mode is requested without a positive duration.
     */
    async evidence({
      modes = EvidenceRuntime.modes,
      before = 0,
      duration = 0,
      target = this.#config.target,
      metadata = null,
      capture = {},
      description = {},
    } = {}) {
      this.#validateModes(modes);
      const output = {};
      if (modes.includes("video")) {
        if (!(duration > 0))
          throw new Error("evidence() video mode requires duration > 0.");
        output.video = await this.record({
          before,
          duration,
          metadata,
        });
      }
      if (modes.includes("capture"))
        output.capture = await this.capture({
          target,
          metadata,
          ...capture,
        });
      if (modes.includes("description"))
        output.description = await this.description({
          target,
          metadata,
          ...description,
        });
      output.markers = this.markers();
      output.diagnostics = this.diagnostics();
      return output;
    }
    /**
     * Handle transfer for scene-evidence processing.
     *
     * @param {string} id
     * @param {RollingTransferOptions} [options]
     * @returns {Promise<SceneValue>} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    async transfer(id, options = {}) {
      if (!this.#descriptions.has(id)) return this.#video.transfer(id, options);
      const send = evidenceGlobal[options.sink ?? "__evidenceSink"];
      if (typeof send !== "function")
        throw new Error("Python evidence sink is unavailable.");
      const sinkFn = /** @type {EvidenceSink} */ (
        /** @type {unknown} */ (send)
      );
      const chunkSize =
        options.chunkSize ?? this.#video.config().transferChunkSize;
      const result = this.#descriptions.get(id);
      if (!result) throw new Error(`Description ${id} is unavailable.`);
      const transferId = evidenceId();
      const manifestBlob = new Blob(
        [JSON.stringify(result.manifest, null, 2)],
        {
          type: "application/json",
        },
      );
      const assets = [
        {
          asset: "description.json",
          blob: manifestBlob,
        },
        ...[...result.files].map(([asset, blob]) => ({
          asset,
          blob,
        })),
      ];
      const publicResult = this.#publicDescription(result);
      const metadata = {
        id: publicResult.id,
        kind: publicResult.kind,
        createdAt: publicResult.createdAt,
        metadata: publicResult.metadata,
        manifestBytes: publicResult.manifestBytes,
        binaryBytes: publicResult.binaryBytes,
        binaryFiles: publicResult.binaryFiles,
      };
      await send({
        event: "transfer-start",
        transferId,
        id,
        kind: "description",
        metadata,
        assetCount: assets.length,
      });
      this.#emit("transferstart", {
        transferId,
        id,
        kind: "description",
      });
      await Promise.all(
        assets.map((asset, index) =>
          this.#transferBlob(
            sinkFn,
            asset.blob,
            {
              transferId,
              id,
              asset: asset.asset,
              assetIndex: index,
              assetCount: assets.length,
              mimeType: asset.blob.type || "application/octet-stream",
            },
            chunkSize,
          ),
        ),
      );
      await send({
        event: "transfer-end",
        transferId,
        id,
        assetCount: assets.length,
      });
      this.#emit("transferend", {
        transferId,
        id,
        kind: "description",
      });
      if (this.#video.config().autoRemoveAfterTransfer) this.remove(id);
      return {
        transferId,
        ...metadata,
      };
    }
    /**
     * Handle remove for scene-evidence processing.
     *
     * @param {string} id
     * @returns {SceneValue} The resulting value.
     */
    remove(id) {
      const videoRemoved = this.#video.remove(id);
      const descriptionRemoved = this.#descriptions.delete(id);
      return videoRemoved || descriptionRemoved;
    }
    /**
     * Handle clear for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    clear() {
      this.#video.clear();
      this.#descriptions.clear();
      this.#markers = [];
      this.#diagnostics = [];
      return this;
    }
    /**
     * Handle mark for scene-evidence processing.
     *
     * @param {string} type
     * @param {unknown} [data]
     * @returns {SceneValue} The resulting value.
     */
    mark(type, data = null) {
      const entry = {
        time: this.#now(),
        type,
        data,
        url: location.href,
      };
      this.#markers.push(entry);
      this.#trimTimeline(this.#markers);
      this.#emit("mark", entry);
      return entry;
    }
    /**
     * Handle markers for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    markers({ since = 0 } = {}) {
      return this.#markers.filter(entry => entry.time >= since);
    }
    /**
     * Handle diagnostics for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    diagnostics({ since = 0 } = {}) {
      return this.#diagnostics.filter(entry => entry.time >= since);
    }
    /**
     * Handle start Diagnostics for scene-evidence processing.
     * @param {Object} options Options.
     * @returns {SceneValue} The resulting value.
     */
    startDiagnostics(options = {}) {
      if (this.#diagnosticCleanup.length || this.#mutationObserver) return this;
      const settings = {
        errors: true,
        mutations: true,
        viewport: true,
        performance: true,
        ...options,
      };
      /** @param {EventTarget} target @param {string} type @param {EventListener} listener @param {boolean} [capture] */
      const listen = (target, type, listener, capture = false) => {
        target.addEventListener(type, listener, capture);
        this.#diagnosticCleanup.push(() =>
          target.removeEventListener(type, listener, capture),
        );
      };
      if (settings.errors) {
        listen(globalThis, "error", event => {
          const errorEvent = /** @type {ErrorEvent} */ (event);
          this.#diagnostic("window-error", {
            message: errorEvent.message,
            source: errorEvent.filename || null,
            line: errorEvent.lineno || null,
            column: errorEvent.colno || null,
          });
        });
        listen(globalThis, "unhandledrejection", event =>
          this.#diagnostic("unhandled-rejection", {
            reason: this.#serializable(
              /** @type {PromiseRejectionEvent} */ (event).reason,
            ),
          }),
        );
      }
      if (settings.viewport) {
        listen(globalThis, "resize", () =>
          this.#diagnostic("viewport-resize", {
            width: innerWidth,
            height: innerHeight,
            devicePixelRatio,
          }),
        );
        const viewport = globalThis.visualViewport;
        viewport &&
          listen(viewport, "resize", () =>
            this.#diagnostic("visual-viewport-resize", {
              width: viewport.width,
              height: viewport.height,
              scale: viewport.scale,
            }),
          );
      }
      if (settings.mutations && document.documentElement) {
        this.#mutationObserver = new MutationObserver(records =>
          this.#diagnostic("dom-mutation", {
            records: records.length,
            attributes: records.filter(record => record.type === "attributes")
              .length,
            childList: records.filter(record => record.type === "childList")
              .length,
            characterData: records.filter(
              record => record.type === "characterData",
            ).length,
            targets: [
              ...new Set(
                records
                  .slice(0, 12)
                  .map(record =>
                    this.#selector(
                      record.target instanceof Element
                        ? record.target
                        : (record.target.parentElement ??
                            document.documentElement),
                    ),
                  ),
              ),
            ].filter(Boolean),
          }),
        );
        this.#mutationObserver.observe(document.documentElement, {
          subtree: true,
          childList: true,
          attributes: true,
          characterData: true,
        });
      }
      if (settings.performance && typeof PerformanceObserver === "function") {
        for (const type of [
          "navigation",
          "resource",
          "paint",
          "longtask",
          "layout-shift",
        ])
          try {
            const observer = new globalThis.PerformanceObserver(list => {
              for (const entry of list.getEntries())
                this.#diagnostic(`performance:${entry.entryType}`, {
                  name: entry.name,
                  startTime: entry.startTime,
                  duration: entry.duration,
                });
            });
            observer.observe({
              type,
              buffered: true,
            });
            this.#performanceObservers.push(observer);
          } catch {
            // Browser does not support this PerformanceObserver entry type.
          }
      }
      return this;
    }
    /**
     * Handle stop Diagnostics for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    stopDiagnostics() {
      this.#diagnosticCleanup.splice(0).forEach(cleanup => {
        cleanup();
      });
      this.#mutationObserver?.disconnect();
      this.#mutationObserver = null;
      this.#performanceObservers.splice(0).forEach(observer => {
        observer.disconnect();
      });
      return this;
    }
    async destroy() {
      this.stopDiagnostics();
      await this.#video
        .disarm({
          force: true,
        })
        .catch(() => null);
      this.clear();
    }
    /**
     * Handle #transfer Blob for scene-evidence processing.
     *
     * @param {EvidenceSink} send
     * @param {Blob} blob
     * @param {Record<string, unknown>} metadata
     * @param {number} chunkSize
     */
    async #transferBlob(send, blob, metadata, chunkSize) {
      const sha256 = await this.#sha256(blob);
      const chunks = Math.ceil(blob.size / chunkSize);
      await send({
        event: "asset-start",
        ...metadata,
        size: blob.size,
        chunks,
        sha256,
      });
      /** @param {number} index @returns {Promise<void>} */
      const sendChunk = async index => {
        if (index >= chunks) return;
        const part = blob.slice(
          index * chunkSize,
          Math.min(blob.size, (index + 1) * chunkSize),
        );
        await send({
          event: "chunk",
          ...metadata,
          index,
          chunks,
          sha256,
          data: await this.#base64(part),
        });
        this.#emit("transferprogress", {
          id: metadata[String("id")],
          asset: metadata[String("asset")],
          index: index + 1,
          chunks,
          progress: (index + 1) / chunks,
        });
        await sendChunk(index + 1);
      };
      await sendChunk(0);
      await send({
        event: "asset-end",
        ...metadata,
        size: blob.size,
        chunks,
        sha256,
      });
    }
    /**
     * Handle #diagnostic for scene-evidence processing.
     *
     * @param {string} type
     * @param {unknown} data
     * @returns {SceneValue} The resulting value.
     */
    #diagnostic(type, data) {
      const entry = {
        time: this.#now(),
        type,
        data,
        url: location.href,
      };
      this.#diagnostics.push(entry);
      this.#trimTimeline(this.#diagnostics);
      this.#emit("diagnostic", entry);
      return entry;
    }
    /**
     * Handle #trim Timeline for scene-evidence processing.
     *
     * @param {EvidenceTimelineEntry[]} list
     */
    #trimTimeline(list) {
      while (list.length > this.#config.maxTimelineEntries) list.shift();
    }
    /**
     * Handle #description Bytes for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    #descriptionBytes() {
      return [...this.#descriptions.values()].reduce(
        (sum, result) => sum + result.manifestBytes + result.binaryBytes,
        0,
      );
    }
    /**
     * Handle #public Description for scene-evidence processing.
     *
     * @param {DescriptionResult} result
     * @returns {SceneValue} The resulting value.
     */
    #publicDescription(result) {
      return {
        id: result.id,
        kind: "description",
        createdAt: result.createdAt,
        metadata: result.metadata,
        manifestBytes: result.manifestBytes,
        binaryBytes: result.binaryBytes,
        manifest: result.manifest,
        binaryFiles: [...result.files].map(([file, blob]) => ({
          file,
          mimeType: blob.type || "application/octet-stream",
          size: blob.size,
        })),
      };
    }
    /**
     * Handle #resolve Target for scene-evidence processing.
     *
     * @param {string|Element|null} target
     * @returns {SceneValue} The resulting value.
     * @throws {Error} When the operation cannot complete.
     */
    #resolveTarget(target) {
      const element =
        typeof target === "string" ? document.querySelector(target) : target;
      if (!(element instanceof Element))
        throw new Error(`Target not found: ${String(target)}`);
      return element;
    }
    /**
     * Handle #selector for scene-evidence processing.
     *
     * @param {Element} element
     * @returns {SceneValue} The resulting value.
     */
    #selector(element) {
      if (!(element instanceof Element)) return null;
      if (element.id) return `#${CSS.escape(element.id)}`;
      return `${element.tagName.toLowerCase()}${[...element.classList]
        .slice(0, 2)
        .map((name) => `.${CSS.escape(name)}`)
        .join("")}`;
    }
    /**
     * Handle #validate Modes for scene-evidence processing.
     *
     * @param {readonly string[]} modes
     * @throws {TypeError} When the operation cannot complete.
     */
    #validateModes(modes) {
      if (
        !Array.isArray(modes) ||
        modes.some(mode => !EvidenceRuntime.modes.includes(mode))
      )
        throw new TypeError(
          `modes must contain only: ${EvidenceRuntime.modes.join(", ")}.`,
        );
    }
    /**
     * Handle #serializable for scene-evidence processing.
     *
     * @param {unknown} value
     * @returns {SceneValue} The resulting value.
     */
    #serializable(value) {
      try {
        return JSON.parse(JSON.stringify(value));
      } catch {
        return String(value);
      }
    }
    /** @param {Blob} blob */
    #sha256 = async blob => {
      const sha = evidenceGlobal.__evidenceSha256;
      if (typeof sha !== "function")
        throw new Error("SHA-256 helper is unavailable.");
      return [
        ...new Uint8Array(
          await /** @type {(buffer:ArrayBuffer)=>Promise<ArrayBuffer>} */ (
            /** @type {unknown} */ (sha)
          )(await blob.arrayBuffer()),
        ),
      ]
        .map(byte => byte.toString(16).padStart(2, "0"))
        .join("");
    };
    /**
     * Handle #base64 for scene-evidence processing.
     *
     * @param {Blob} blob
     * @returns {SceneValue} The resulting value.
     */
    #base64(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(reader.error);
        reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
        reader.readAsDataURL(blob);
      });
    }
    /**
     * Handle #now for scene-evidence processing.
     * @returns {SceneValue} The resulting value.
     */
    #now() {
      return performance.timeOrigin + performance.now();
    }
    /**
     * Handle #emit for scene-evidence processing.
     *
     * @param {string} type
     * @param {unknown} [detail]
     * @returns {SceneValue} The resulting value.
     */
    #emit(type, detail = {}) {
      const data = {
        type,
        timestamp: new Date().toISOString(),
        ...(detail && typeof detail === "object"
          ? detail
          : {
              detail,
            }),
      };
      this.dispatchEvent(
        new CustomEvent(type, {
          detail: data,
        }),
      );
      globalThis.dispatchEvent?.(
        new CustomEvent(`${this.#config.eventPrefix}:${type}`, {
          detail: data,
        }),
      );
      return data;
    }
  }
  Object.defineProperties(globalThis, {
    RollingCapture: {
      value: RollingCapture,
      configurable: true,
    },
    EvidenceRuntime: {
      value: EvidenceRuntime,
      configurable: true,
    },
  });
})();
