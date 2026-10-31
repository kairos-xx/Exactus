/** Ambient declarations for the untyped `optimal-select` package. */
declare module "optimal-select" {
	export function getSingleSelector(element: unknown, options?: unknown): string;
	export function getMultiSelector(elements: unknown, options?: unknown): string;
	export function optimize(selector: string, elements?: unknown, options?: unknown): string;
	const optimalSelect: {
		getSingleSelector: typeof getSingleSelector;
		getMultiSelector: typeof getMultiSelector;
		optimize: typeof optimize;
	};
	export default optimalSelect;
}
