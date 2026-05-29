export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatMoney(value: string | null) {
  if (value === null) {
    return "-";
  }

  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return value;
  }

  return new Intl.NumberFormat("th-TH", {
    style: "currency",
    currency: "THB",
  }).format(amount);
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "แบบร่าง",
    approved: "อนุมัติแล้ว",
    rejected: "ปฏิเสธแล้ว",
    completed: "เสร็จสิ้น",
    imported: "นำเข้าแล้ว",
    failed: "ล้มเหลว",
    running: "กำลังทำงาน",
    success: "สำเร็จ",
    waiting_for_generated_images: "รอรูปที่สร้างแล้ว",
  };

  return labels[status] ?? status;
}

export function imageTypeLabel(imageType: string) {
  const labels: Record<string, string> = {
    product: "รูปสินค้า",
    lifestyle: "รูปใช้งานจริง",
    detail: "รูปถ่ายใกล้",
    size_chart: "ตารางไซซ์",
    brief: "รูปอ้างอิง",
  };

  return labels[imageType] ?? imageType;
}

export function jobTypeLabel(jobType: string) {
  const labels: Record<string, string> = {
    product_sync: "ส่งสินค้าเข้า LINE",
    product_publish: "เปิดขายบน LINE",
    product_hide: "ซ่อนสินค้าบน LINE",
    line_status_refresh: "ดึงสถานะจาก LINE",
  };

  return labels[jobType] ?? jobType;
}

export function targetTypeLabel(targetType: string) {
  const labels: Record<string, string> = {
    product: "สินค้า",
    product_image: "รูปสินค้า",
  };

  return labels[targetType] ?? targetType;
}

export function statusClassName(status: string) {
  const classes: Record<string, string> = {
    draft: "bg-amber-50 text-amber-800 ring-amber-200",
    approved: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    rejected: "bg-rose-50 text-rose-800 ring-rose-200",
    completed: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    failed: "bg-rose-50 text-rose-800 ring-rose-200",
    running: "bg-sky-50 text-sky-800 ring-sky-200",
    success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  };

  return classes[status] ?? "bg-zinc-100 text-zinc-700 ring-zinc-200";
}

type DisplayStatusSource = {
  isDisplay?: boolean | null;
  is_display?: boolean | null;
  hidden?: boolean | null;
};

export function displayStatusLabel(source: DisplayStatusSource) {
  const isDisplay = source.isDisplay ?? source.is_display;
  if (typeof isDisplay === "boolean") {
    return isDisplay ? "เปิดขาย" : "ซ่อนอยู่";
  }
  if (typeof source.hidden === "boolean") {
    return source.hidden ? "ซ่อนอยู่" : "เปิดขาย";
  }
  return "ยังไม่มีข้อมูล";
}

export function displayStatusClassName(source: DisplayStatusSource) {
  const label = displayStatusLabel(source);
  if (label === "เปิดขาย") {
    return "bg-emerald-50 text-emerald-800 ring-emerald-200";
  }
  if (label === "ซ่อนอยู่") {
    return "bg-zinc-100 text-zinc-700 ring-zinc-200";
  }
  return "bg-amber-50 text-amber-800 ring-amber-200";
}
