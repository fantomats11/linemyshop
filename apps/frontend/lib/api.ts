const API_PROXY_BASE = "/api/backend";

export type ProductSummary = {
  id: number;
  product_group: string;
  name: string;
  color: string;
  gender: string;
  category: string;
  status: string;
  variant_count: number;
  total_stock: number;
  total_available_stock: number;
  image_url: string | null;
  created_at: string;
  updated_at: string;
  external_product_id?: string | null;
  sync_status?: string | null;
  last_synced_at?: string | null;
  line_last_refreshed_at?: string | null;
  isDisplay?: boolean | null;
  is_display?: boolean | null;
  hidden?: boolean | null;
};

export type ProductImage = {
  id: number;
  url: string;
  position: number;
  status: string;
  image_type: string;
  is_main: boolean;
  review_note: string | null;
};

export type Inventory = {
  stock_on_hand: number;
  reserved_stock: number;
  available_stock: number;
};

export type MeasurementField = {
  label: string;
  value: string;
};

export type ProductVariant = {
  id: number;
  sku: string;
  barcode: string | null;
  size: string;
  waist: string;
  hip: string;
  length: string;
  measurements: MeasurementField[];
  price: string;
  sale_price: string | null;
  status: string;
  inventory: Inventory | null;
};

export type ProductDetail = {
  id: number;
  product_group: string;
  name: string;
  color: string;
  gender: string;
  category: string;
  description: string | null;
  note: string | null;
  status: string;
  images: ProductImage[];
  variants: ProductVariant[];
  external_product_id?: string | null;
  sync_status?: string | null;
  last_synced_at?: string | null;
  line_last_refreshed_at?: string | null;
  isDisplay?: boolean | null;
  is_display?: boolean | null;
  hidden?: boolean | null;
};

export type ImportBatch = {
  id: number;
  source_file: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  status: string;
  created_at: string;
};

export type ImportError = {
  id: number;
  import_batch_id: number;
  row_number: number;
  sku: string | null;
  product_group: string | null;
  error_message: string;
  created_at: string;
};

export type ProductSyncResponse = {
  product_id: number;
  sync_job_id: number;
  status: string;
  mock_mode: boolean;
  external_product_id: string | null;
  variants_synced: number;
  warnings: string[];
  message: string;
};

export type ProductLineStatusResponse = {
  product_id: number;
  sync_job_id: number | null;
  status: string;
  mock_mode: boolean;
  external_product_id: string;
  is_display: boolean | null;
  message: string;
  warnings: string[];
};

export type ProductSyncReadiness = {
  product_id: number;
  ready: boolean;
  mock_mode: boolean;
  errors: string[];
  warnings: string[];
};

export type ProductSyncPreview = {
  product_id: number;
  ready: boolean;
  mock_mode: boolean;
  action: string;
  endpoint: string;
  method: string;
  errors: string[];
  warnings: string[];
  internal_payload: Record<string, unknown>;
  outbound_payload: Record<string, unknown> | null;
};

export type ImageGenerationSlot = {
  position: number;
  image_type: string;
  title: string;
  prompt: string;
  required: boolean;
};

export type ProductImageGenerationBrief = {
  product_id: number;
  ready: boolean;
  errors: string[];
  warnings: string[];
  reference_images: ProductImage[];
  slots: ImageGenerationSlot[];
};

export type ImageGenerationJob = {
  id: number;
  product_id: number;
  status: string;
  mode: string;
  prompt_payload: Record<string, unknown>;
  result_payload: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type SyncJob = {
  id: number;
  job_type: string;
  target_type: string;
  target_id: number;
  status: string;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type CreateProductImageInput = {
  url: string;
  image_type: string;
  position: number;
};

export type CreateProductVariantInput = {
  sku: string;
  barcode?: string | null;
  size: string;
  waist?: string;
  hip?: string;
  length?: string;
  measurements?: MeasurementField[];
  price: string;
  sale_price?: string | null;
  stock_on_hand: number;
  reserved_stock?: number;
  status?: string;
};

export type CreateProductInput = {
  product_group: string;
  name: string;
  color: string;
  gender: string;
  category: string;
  description?: string | null;
  note?: string | null;
  status?: string;
  variants: CreateProductVariantInput[];
};

export type UpdateProductInput = Partial<{
  name: string;
  color: string;
  gender: string;
  category: string;
  description: string | null;
  note: string | null;
}>;

export type UpdateProductVariantInput = Partial<{
  barcode: string | null;
  size: string;
  waist: string;
  hip: string;
  length: string;
  measurements: MeasurementField[];
  price: string;
  sale_price: string | null;
  status: string;
}>;

export type UpdateInventoryInput = Partial<{
  stock_on_hand: number;
  reserved_stock: number;
}>;

export type CsvValidationResponse = {
  input_file: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  total_errors: number;
  total_warnings: number;
  output_files: Record<string, string>;
};

export type RunImportResponse = {
  source_file: string;
  total_rows: number;
  products_created: number;
  products_updated: number;
  variants_created: number;
  variants_updated: number;
  inventory_created: number;
  inventory_updated: number;
  images_created: number;
  errors: Array<{
    row_number: number;
    sku: string | null;
    product_group: string | null;
    error_message: string;
  }>;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PROXY_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (errorBody.detail) {
        message =
          typeof errorBody.detail === "string"
            ? errorBody.detail
            : JSON.stringify(errorBody.detail);
      }
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_PROXY_BASE}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (errorBody.detail) {
        message =
          typeof errorBody.detail === "string"
            ? errorBody.detail
            : JSON.stringify(errorBody.detail);
      }
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export function listProducts() {
  return request<ProductSummary[]>("/products");
}

export function getProduct(productId: string | number) {
  return request<ProductDetail>(`/products/${productId}`);
}

export function createProduct(input: CreateProductInput) {
  return request<ProductDetail>("/products", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateProduct(productId: string | number, input: UpdateProductInput) {
  return request<ProductDetail>(`/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function approveProduct(productId: string | number) {
  return request<ProductSummary>(`/products/${productId}/approve`, {
    method: "POST",
  });
}

export function rejectProduct(productId: string | number, reason: string) {
  return request<ProductSummary>(`/products/${productId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function archiveProduct(productId: string | number, reason: string | null = null) {
  return request<ProductSummary>(`/products/${productId}/archive`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function createProductImage(
  productId: string | number,
  input: CreateProductImageInput,
) {
  return request<ProductImage>(`/products/${productId}/images`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function uploadProductReferenceImages(productId: string | number, files: File[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return uploadRequest<ProductImage[]>(
    `/products/${productId}/reference-images`,
    formData,
  );
}

export function getProductImageGenerationBrief(productId: string | number) {
  return request<ProductImageGenerationBrief>(
    `/products/${productId}/image-generation-brief`,
  );
}

export function createImageGenerationJob(productId: string | number) {
  return request<ImageGenerationJob>(`/products/${productId}/image-generation-jobs`, {
    method: "POST",
  });
}

export function getImageGenerationJob(jobId: string | number) {
  return request<ImageGenerationJob>(`/image-generation-jobs/${jobId}`);
}

export function runImageGenerationJob(
  jobId: string | number,
  options?: {
    slotPositions?: number[];
    quality?: string;
    imageSize?: string;
    outputFormat?: string;
    numImagesPerSlot?: number;
    approve?: boolean;
    setMainPosition?: number;
  },
) {
  return request<ImageGenerationJob>(`/image-generation-jobs/${jobId}/run`, {
    method: "POST",
    body: JSON.stringify({
      ...(options?.slotPositions ? { slot_positions: options.slotPositions } : {}),
      ...(options?.quality ? { quality: options.quality } : {}),
      ...(options?.imageSize ? { image_size: options.imageSize } : {}),
      ...(options?.outputFormat ? { output_format: options.outputFormat } : {}),
      ...(options?.numImagesPerSlot
        ? { num_images_per_slot: options.numImagesPerSlot }
        : {}),
      ...(options?.approve === undefined ? {} : { approve: options.approve }),
      ...(options?.setMainPosition
        ? { set_main_position: options.setMainPosition }
        : {}),
    }),
  });
}

export function uploadGeneratedImagesForJob(
  jobId: string | number,
  files: File[],
  options?: {
    approve?: boolean;
    setMainIndex?: number;
    imageTypes?: string[];
  },
) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  for (const imageType of options?.imageTypes ?? []) {
    formData.append("image_types", imageType);
  }
  formData.append("approve", String(options?.approve ?? false));
  formData.append("set_main_index", String(options?.setMainIndex ?? 1));
  return uploadRequest<ProductImage[]>(
    `/image-generation-jobs/${jobId}/generated-images`,
    formData,
  );
}

export function approveProductImage(imageId: string | number, reviewNote?: string | null) {
  return request<ProductImage>(`/product-images/${imageId}/approve`, {
    method: "POST",
    body: JSON.stringify({ review_note: reviewNote ?? null }),
  });
}

export function rejectProductImage(imageId: string | number, reviewNote?: string | null) {
  return request<ProductImage>(`/product-images/${imageId}/reject`, {
    method: "POST",
    body: JSON.stringify({ review_note: reviewNote ?? null }),
  });
}

export function setMainProductImage(imageId: string | number) {
  return request<ProductImage>(`/product-images/${imageId}/set-main`, {
    method: "POST",
  });
}

export function updateProductVariant(
  variantId: string | number,
  input: UpdateProductVariantInput,
) {
  return request<ProductVariant>(`/product-variants/${variantId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function updateVariantInventory(
  variantId: string | number,
  input: UpdateInventoryInput,
) {
  return request<Inventory>(`/product-variants/${variantId}/inventory`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function listImports() {
  return request<ImportBatch[]>("/imports");
}

export function validateCsvImport(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return uploadRequest<CsvValidationResponse>("/imports/validate-csv", formData);
}

export function runCsvImport(validProductsPath: string, dryRun = false) {
  return request<RunImportResponse>("/imports/run", {
    method: "POST",
    body: JSON.stringify({
      valid_products_path: validProductsPath,
      dry_run: dryRun,
    }),
  });
}

export function listImportErrors(importBatchId: string | number) {
  return request<ImportError[]>(`/imports/${importBatchId}/errors`);
}

export function getProductSyncReadiness(productId: string | number) {
  return request<ProductSyncReadiness>(`/products/${productId}/sync-readiness`);
}

export function previewProductSync(productId: string | number) {
  return request<ProductSyncPreview>(`/products/${productId}/sync/preview`, {
    method: "POST",
  });
}

export function syncProduct(productId: string | number, confirm?: string) {
  return request<ProductSyncResponse>(`/products/${productId}/sync`, {
    method: "POST",
    body: JSON.stringify(confirm ? { confirm } : {}),
  });
}

export function refreshProductLineStatus(productId: string | number) {
  return request<ProductLineStatusResponse>(
    `/products/${productId}/line-status/refresh`,
    {
      method: "POST",
    },
  );
}

export function publishProduct(productId: string | number, confirm?: string) {
  return request<ProductLineStatusResponse>(`/products/${productId}/publish`, {
    method: "POST",
    body: JSON.stringify(confirm ? { confirm } : {}),
  });
}

export function hideProduct(
  productId: string | number,
  confirm?: string,
  reason?: string | null,
) {
  return request<ProductLineStatusResponse>(`/products/${productId}/hide`, {
    method: "POST",
    body: JSON.stringify({
      ...(confirm ? { confirm } : {}),
      ...(reason ? { reason } : {}),
    }),
  });
}

export function listSyncJobs() {
  return request<SyncJob[]>("/sync-jobs");
}

export function getSyncJob(syncJobId: string | number) {
  return request<SyncJob>(`/sync-jobs/${syncJobId}`);
}
