"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { listSyncJobs, SyncJob } from "../../lib/api";
import { formatDateTime, jobTypeLabel, targetTypeLabel } from "../../lib/format";
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

function formatOptionalDateTime(value: string | null) {
  return value ? formatDateTime(value) : "-";
}

export default function SyncJobsPage() {
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSyncJobs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setSyncJobs(await listSyncJobs());
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "ไม่สามารถโหลดประวัติการส่ง LINE ได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSyncJobs();
  }, [loadSyncJobs]);

  const successCount = syncJobs.filter((job) => job.status === "success").length;
  const runningCount = syncJobs.filter((job) => job.status === "running").length;
  const failedCount = syncJobs.filter((job) => job.status === "failed").length;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="ประวัติการส่ง LINE"
        title="ประวัติการทำงาน"
        description="ตรวจสอบรายการที่ระบบส่งสินค้า เปิดขาย ซ่อนสินค้า หรือดึงสถานะจาก LINE MyShop"
      />

      {error ? <ErrorPanel message={error} onRetry={loadSyncJobs} /> : null}

      {isLoading ? (
        <LoadingPanel />
      ) : syncJobs.length === 0 ? (
        <EmptyPanel>ยังไม่มีประวัติการทำงาน</EmptyPanel>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="รายการทั้งหมด" value={syncJobs.length} />
            <StatCard label="สำเร็จ" value={successCount} tone="emerald" />
            <StatCard label="กำลังทำงาน" value={runningCount} tone="sky" />
            <StatCard label="ล้มเหลว" value={failedCount} tone="rose" />
          </div>

          <TableShell>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">งานที่ทำ</th>
                  <th className="px-4 py-3">ประเภทข้อมูล</th>
                  <th className="px-4 py-3 text-right">รหัสข้อมูล</th>
                  <th className="px-4 py-3">สถานะ</th>
                  <th className="px-4 py-3">ข้อความผิดพลาด</th>
                  <th className="px-4 py-3">สร้างเมื่อ</th>
                  <th className="px-4 py-3">เริ่มเมื่อ</th>
                  <th className="px-4 py-3">เสร็จเมื่อ</th>
                  <th className="px-4 py-3 text-right">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white">
                {syncJobs.map((syncJob) => (
                  <tr key={syncJob.id} className="hover:bg-sky-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-zinc-900">
                      {syncJob.id}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {jobTypeLabel(syncJob.job_type)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {targetTypeLabel(syncJob.target_type)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {syncJob.target_id}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge status={syncJob.status} />
                    </td>
                    <td className="min-w-56 px-4 py-3 text-zinc-700">
                      {syncJob.error_message ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                      {formatDateTime(syncJob.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                      {formatOptionalDateTime(syncJob.started_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                      {formatOptionalDateTime(syncJob.finished_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/sync-jobs/${syncJob.id}`} className={actionLinkClassName}>
                        ดู
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
