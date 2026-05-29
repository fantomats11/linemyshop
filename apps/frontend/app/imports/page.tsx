"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  CsvValidationResponse,
  ImportBatch,
  listImports,
  RunImportResponse,
  runCsvImport,
  validateCsvImport,
} from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import {
  actionLinkClassName,
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  StatCard,
  StatusBadge,
  TableShell,
} from "../../lib/ui";

export default function ImportsPage() {
  const [imports, setImports] = useState<ImportBatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<CsvValidationResponse | null>(null);
  const [importResult, setImportResult] = useState<RunImportResponse | null>(null);
  const [isImportActionLoading, setIsImportActionLoading] = useState(false);

  const loadImports = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setImports(await listImports());
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "ไม่สามารถโหลดรายการ import ได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadImports();
  }, [loadImports]);

  const totalRows = imports.reduce((sum, importBatch) => sum + importBatch.total_rows, 0);
  const validRows = imports.reduce((sum, importBatch) => sum + importBatch.valid_rows, 0);
  const invalidRows = imports.reduce((sum, importBatch) => sum + importBatch.invalid_rows, 0);

  async function handleValidateCsv() {
    if (!selectedFile) {
      setError("กรุณาเลือกไฟล์ CSV");
      return;
    }
    setIsImportActionLoading(true);
    setError(null);
    setValidationResult(null);
    setImportResult(null);
    try {
      setValidationResult(await validateCsvImport(selectedFile));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "ไม่สามารถ validate CSV ได้",
      );
    } finally {
      setIsImportActionLoading(false);
    }
  }

  async function handleRunImport(dryRun: boolean) {
    const validProductsPath = validationResult?.output_files.valid_products;
    if (!validProductsPath) {
      setError("ยังไม่มี valid_products.csv จากการ validate");
      return;
    }
    setIsImportActionLoading(true);
    setError(null);
    setImportResult(null);
    try {
      setImportResult(await runCsvImport(validProductsPath, dryRun));
      await loadImports();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "ไม่สามารถ import CSV ได้",
      );
    } finally {
      setIsImportActionLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="นำเข้าข้อมูลสินค้า"
        title="นำเข้า Product Master CSV"
        description="อัปโหลดไฟล์ CSV ตรวจข้อมูลก่อนนำเข้า แล้วค่อยบันทึกสินค้าเข้าระบบ"
      />

      {error ? <ErrorPanel message={error} onRetry={loadImports} /> : null}

      <section className="space-y-4 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">อัปโหลดไฟล์สินค้า</h2>
          <p className="mt-1 text-sm text-zinc-500">
            เลือกไฟล์ CSV จาก template แล้วกดตรวจสอบก่อนนำเข้าจริง
          </p>
        </div>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto]">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            className="rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm"
          />
          <button
            type="button"
            disabled={isImportActionLoading}
            onClick={() => void handleValidateCsv()}
            className={actionLinkClassName}
          >
            ตรวจไฟล์
          </button>
          <button
            type="button"
            disabled={isImportActionLoading || !validationResult}
            onClick={() => void handleRunImport(true)}
            className={actionLinkClassName}
          >
            ทดลองนำเข้า
          </button>
          <button
            type="button"
            disabled={isImportActionLoading || !validationResult || validationResult.invalid_rows > 0}
            onClick={() => void handleRunImport(false)}
            className="inline-flex items-center justify-center rounded-md border border-zinc-950 bg-zinc-950 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            นำเข้าจริง
          </button>
        </div>

        {validationResult ? (
          <div className="rounded-md border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950">
            <div className="font-semibold">ผลตรวจไฟล์</div>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <div><dt className="text-xs opacity-70">แถวทั้งหมด</dt><dd className="font-semibold">{validationResult.total_rows}</dd></div>
              <div><dt className="text-xs opacity-70">ใช้ได้</dt><dd className="font-semibold">{validationResult.valid_rows}</dd></div>
              <div><dt className="text-xs opacity-70">ต้องแก้</dt><dd className="font-semibold">{validationResult.invalid_rows}</dd></div>
              <div><dt className="text-xs opacity-70">ข้อผิดพลาด</dt><dd className="font-semibold">{validationResult.total_errors}</dd></div>
              <div><dt className="text-xs opacity-70">คำเตือน</dt><dd className="font-semibold">{validationResult.total_warnings}</dd></div>
            </dl>
            <div className="mt-3 break-all text-xs">
              valid_products.csv: {validationResult.output_files.valid_products}
            </div>
          </div>
        ) : null}

        {importResult ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950">
            <div className="font-semibold">ผลนำเข้า</div>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-xs opacity-70">สินค้าใหม่</dt><dd className="font-semibold">{importResult.products_created}</dd></div>
              <div><dt className="text-xs opacity-70">สินค้าอัปเดต</dt><dd className="font-semibold">{importResult.products_updated}</dd></div>
              <div><dt className="text-xs opacity-70">SKU ใหม่</dt><dd className="font-semibold">{importResult.variants_created}</dd></div>
              <div><dt className="text-xs opacity-70">SKU อัปเดต</dt><dd className="font-semibold">{importResult.variants_updated}</dd></div>
            </dl>
            {importResult.errors.length > 0 ? (
              <div className="mt-3 text-rose-800">ข้อผิดพลาด: {importResult.errors.length}</div>
            ) : null}
          </div>
        ) : null}
      </section>

      {isLoading ? (
        <LoadingPanel />
      ) : imports.length === 0 ? (
        <EmptyPanel>ยังไม่มีประวัติการนำเข้า</EmptyPanel>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="รอบนำเข้า" value={imports.length} />
            <StatCard label="แถวทั้งหมด" value={totalRows} tone="sky" />
            <StatCard label="แถวที่ผ่าน" value={validRows} tone="emerald" />
            <StatCard label="แถวที่ต้องแก้" value={invalidRows} tone="rose" />
          </div>

          <TableShell>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">ไฟล์ต้นทาง</th>
                  <th className="px-4 py-3 text-right">แถวทั้งหมด</th>
                  <th className="px-4 py-3 text-right">ใช้ได้</th>
                  <th className="px-4 py-3 text-right">ต้องแก้</th>
                  <th className="px-4 py-3">สถานะ</th>
                  <th className="px-4 py-3">วันที่นำเข้า</th>
                  <th className="px-4 py-3 text-right">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white">
                {imports.map((importBatch) => (
                  <tr key={importBatch.id} className="hover:bg-sky-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-zinc-900">
                      {importBatch.id}
                    </td>
                    <td className="min-w-64 px-4 py-3 text-zinc-700">
                      {importBatch.source_file}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {importBatch.total_rows}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {importBatch.valid_rows}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {importBatch.invalid_rows}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge status={importBatch.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                      {formatDateTime(importBatch.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/imports/${importBatch.id}`}
                        className={actionLinkClassName}
                      >
                        ดูข้อผิดพลาด
                      </Link>
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
