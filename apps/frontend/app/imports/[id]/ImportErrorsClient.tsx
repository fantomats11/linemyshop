"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ImportError, listImportErrors } from "../../../lib/api";
import { formatDateTime } from "../../../lib/format";
import {
  actionLinkClassName,
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  StatCard,
  TableShell,
} from "../../../lib/ui";

type ImportErrorsPageProps = {
  importBatchId: string;
};

export default function ImportErrorsClient({ importBatchId }: ImportErrorsPageProps) {
  const [errors, setErrors] = useState<ImportError[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadErrors = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setErrors(await listImportErrors(importBatchId));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "ไม่สามารถโหลด import errors ได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, [importBatchId]);

  useEffect(() => {
    void loadErrors();
  }, [loadErrors]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Import Batch ID: ${importBatchId}`}
        title="Import Errors"
        description="รายการ row ที่ไม่ผ่าน validation หรือ import เพื่อใช้แก้ข้อมูลต้นทาง"
        action={
        <Link
          href="/imports"
            className={actionLinkClassName}
        >
          กลับไปประวัติ Import
        </Link>
        }
      />

      {error ? <ErrorPanel message={error} onRetry={loadErrors} /> : null}

      {isLoading ? (
        <LoadingPanel />
      ) : errors.length === 0 ? (
        <div className="space-y-3">
          <StatCard label="Errors" value={0} tone="emerald" />
          <EmptyPanel>ไม่พบ error สำหรับ import batch นี้</EmptyPanel>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Errors" value={errors.length} tone="rose" />
            <StatCard
              label="Rows แรก"
              value={Math.min(...errors.map((importError) => importError.row_number))}
              tone="amber"
            />
            <StatCard
              label="Rows ล่าสุด"
              value={Math.max(...errors.map((importError) => importError.row_number))}
              tone="sky"
            />
          </div>

          <TableShell>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">แถวที่</th>
                  <th className="px-4 py-3">SKU</th>
                  <th className="px-4 py-3">กลุ่มสินค้า</th>
                  <th className="px-4 py-3">ข้อความผิดพลาด</th>
                  <th className="px-4 py-3">พบเมื่อ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white">
                {errors.map((importError) => (
                  <tr key={importError.id} className="hover:bg-sky-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-zinc-900">
                      {importError.row_number}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {importError.sku ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {importError.product_group ?? "-"}
                    </td>
                    <td className="min-w-80 px-4 py-3 text-zinc-700">
                      {importError.error_message}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                      {formatDateTime(importError.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        </>
      )}
    </div>
  );
}
