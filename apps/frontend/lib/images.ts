export function isBriefImageUrl(url: string | null | undefined) {
  return Boolean(url?.trim().startsWith("data/input/images/"));
}

export function isRenderableProductImageUrl(url: string | null | undefined) {
  const trimmedUrl = url?.trim();
  if (!trimmedUrl || isBriefImageUrl(trimmedUrl)) {
    return false;
  }

  return (
    trimmedUrl.startsWith("http://") ||
    trimmedUrl.startsWith("https://") ||
    trimmedUrl.startsWith("/")
  );
}

export function productImageUrls(urls: Array<string | null | undefined>) {
  return urls.filter(isRenderableProductImageUrl) as string[];
}

export function hasBriefImageOnly(urls: Array<string | null | undefined>) {
  return urls.some(isBriefImageUrl) && productImageUrls(urls).length === 0;
}

type ProductImageLike = {
  url: string;
  image_type?: string;
  status?: string;
};

export function isBriefImage(image: ProductImageLike) {
  return image.image_type === "brief" || isBriefImageUrl(image.url);
}

export function isApprovedStorefrontImage(image: ProductImageLike) {
  return (
    image.status === "approved" &&
    !isBriefImage(image) &&
    isRenderableProductImageUrl(image.url)
  );
}
