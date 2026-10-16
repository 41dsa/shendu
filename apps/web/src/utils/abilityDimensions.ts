/** 与 services/api/app/domain/essay.py ABILITY_DIMENSIONS 对齐 */

export const ABILITY_DIMENSIONS: { id: string; name: string }[] = [
  { id: "A1", name: "立意与审题" },
  { id: "A2", name: "结构与层次" },
  { id: "A3", name: "论证与素材" },
  { id: "A4", name: "语言表达" },
  { id: "A5", name: "规范与字数" },
];

export function abilityName(id: string | null | undefined): string | null {
  if (!id) return null;
  return ABILITY_DIMENSIONS.find((d) => d.id === id)?.name ?? null;
}
