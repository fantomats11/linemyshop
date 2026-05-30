import categories from "./categories_v2.generated.json";

export type ProductCategoryOption = {
  id: number;
  en: string;
  th: string;
  fda?: string;
  fdaAds?: string;
  tisi?: string;
};

export const allProductCategoryOptions = categories as ProductCategoryOption[];

const lineMyShopRelevantCategoryIds = new Set([
  32,
  33,
  34,
  35,
  36,
  37,
  38,
  39,
  40,
  41,
  42,
  44,
  45,
  46,
  47,
  48,
  49,
  50,
  52,
  53,
  54,
  56,
  57,
  58,
  59,
  60,
  61,
  62,
  63,
  64,
  65,
  66,
  67,
  68,
  69,
  70,
  71,
  190,
  191,
  192,
  193,
  194,
  210,
  211,
]);

export const productCategoryOptions = allProductCategoryOptions.filter((category) =>
  lineMyShopRelevantCategoryIds.has(category.id),
);

export function categoryLabel(category: ProductCategoryOption) {
  return `${category.th} (#${category.id})`;
}

export function categoryLeafLabel(category: ProductCategoryOption) {
  const parts = category.th.split(">");
  return `${parts[parts.length - 1]} (#${category.id})`;
}

export function categoryGroupName(category: string) {
  return category.split(">")[0] ?? category;
}

const productCategoryGroupMap = new Map<string, ProductCategoryOption[]>();

for (const category of productCategoryOptions) {
  const groupName = categoryGroupName(category.th);
  productCategoryGroupMap.set(groupName, [
    ...(productCategoryGroupMap.get(groupName) ?? []),
    category,
  ]);
}

export const productCategoryGroups = Array.from(
  productCategoryGroupMap,
  ([label, options]) => ({ label, options }),
);

export function inferGenderFromCategory(category: string) {
  const lower = category.toLowerCase();
  if (lower.includes("men's") || category.includes("ผู้ชาย")) {
    return "ชาย";
  }
  if (lower.includes("women's") || category.includes("ผู้หญิง")) {
    return "หญิง";
  }
  if (
    lower.includes("unisex") ||
    category.includes("Unisex") ||
    category.includes("ทุกเพศ")
  ) {
    return "Unisex";
  }
  return null;
}

export function categoryMeasurementPreset(category: string) {
  const lower = category.toLowerCase();
  if (lower.includes("shoes") || category.includes("รองเท้า")) {
    return ["ความยาวเท้า", "EU", "US"];
  }
  if (lower.includes("bag") || category.includes("กระเป๋า")) {
    return ["กว้าง", "สูง", "ลึก"];
  }
  if (lower.includes("socks") || category.includes("ถุงเท้า")) {
    return ["ความยาวเท้า", "ความสูงถุงเท้า", "รอบน่อง"];
  }
  if (lower.includes("headwear") || category.includes("หมวก")) {
    return ["รอบศีรษะ", "ปีกหมวก", "ความสูง"];
  }
  if (lower.includes("gloves") || category.includes("ถุงมือ")) {
    return ["รอบฝ่ามือ", "ความยาวมือ", "ความยาวนิ้ว"];
  }
  if (
    lower.includes("bottoms") ||
    lower.includes("skirt") ||
    category.includes("กางเกง") ||
    category.includes("กระโปรง")
  ) {
    return ["เอว", "สะโพก", "ความยาว"];
  }
  if (
    lower.includes("tops") ||
    lower.includes("dress") ||
    lower.includes("sleepwear") ||
    lower.includes("sportswear") ||
    lower.includes("activewear") ||
    lower.includes("swimwear") ||
    category.includes("เสื้อ") ||
    category.includes("เดรส") ||
    category.includes("ชุด")
  ) {
    return ["รอบอก", "ไหล่", "ความยาว"];
  }
  return ["ขนาด 1", "ขนาด 2", "ความยาว"];
}
