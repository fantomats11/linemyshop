"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getSyncJob, SyncJob } from "../../../lib/api";
import { formatDateTime, jobTypeLabel, statusLabel, targetTypeLabel } from "../../../lib/format";
import {
  actionLinkClassName,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  StatCard,
  StatusBadge,
} from "../../../lib/ui";

type SyncJobDetailClientProps = {
  syncJobId: string;
};

function formatOptionalDateTime(value: string | null) {
  return value ? formatDateTime(value) : "-";
}

export default function SyncJobDetailClient({ syncJobId }: SyncJobDetailClientProps) {
  const [syncJob, setSyncJob] = useState<SyncJob | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSyncJob = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setSyncJob(await getSyncJob(syncJobId));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "ไม่สามารถโหลดประวัติการทำงานได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, [syncJobId]);

  useEffect(() => {
    void loadSyncJob();
  }, [loadSyncJob]);

  if (isLoading) {
    return <LoadingPanel />;
  }

  if (!syncJob) {
    return (
      <div className="space-y-4">
        <ErrorPanel message={error ?? "ไม่พบประวัติการทำงาน"} onRetry={loadSyncJob} />
        <Link href="/sync-jobs" className={actionLinkClassName}>
          กลับไปประวัติการส่ง LINE
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`รหัสงาน: ${syncJob.id}`}
        title="รายละเอียดการทำงาน"
        description="ดูสถานะ เวลาเริ่ม เวลาจบ และข้อความผิดพลาดจากการส่งข้อมูลไป LINE MyShop"
        action={<StatusBadge status={syncJob.status} />}
      />

      {error ? <ErrorPanel message={error} onRetry={loadSyncJob} /> : null}

      <div className="flex flex-wrap gap-2">
        <Link href="/sync-jobs" className={actionLinkClassName}>
          กลับไปประวัติการส่ง LINE
        </Link>
        {syncJob.target_type === "product" ? (
          <Link href={`/products/${syncJob.target_id}`} className={actionLinkClassName}>
            ดูสินค้า
          </Link>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="งานที่ทำ" value={jobTypeLabel(syncJob.job_type)} />
        <StatCard label="ประเภทข้อมูล" value={targetTypeLabel(syncJob.target_type)} tone="sky" />
        <StatCard label="รหัสข้อมูล" value={syncJob.target_id} />
        <StatCard
          label="สถานะ"
          value={statusLabel(syncJob.status)}
          tone={syncJob.status === "failed" ? "rose" : "emerald"}
        />
      </div>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-950">ข้อมูล Sync Job</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-xs font-medium text-zinc-500">ID</dt>
            <dd className="mt-1 text-sm text-zinc-900">{syncJob.id}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">งานที่ทำ</dt>
            <dd className="mt-1 text-sm text-zinc-900">{jobTypeLabel(syncJob.job_type)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">ประเภทข้อมูล</dt>
            <dd className="mt-1 text-sm text-zinc-900">{targetTypeLabel(syncJob.target_type)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">รหัสข้อมูล</dt>
            <dd className="mt-1 text-sm text-zinc-900">{syncJob.target_id}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">สร้างเมื่อ</dt>
            <dd className="mt-1 text-sm text-zinc-900">
              {formatDateTime(syncJob.created_at)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">เริ่มเมื่อ</dt>
            <dd className="mt-1 text-sm text-zinc-900">
              {formatOptionalDateTime(syncJob.started_at)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">เสร็จเมื่อ</dt>
            <dd className="mt-1 text-sm text-zinc-900">
              {formatOptionalDateTime(syncJob.finished_at)}
            </dd>
          </div>
          <div className="sm:col-span-2 lg:col-span-3">
            <dt className="text-xs font-medium text-zinc-500">ข้อความผิดพลาด</dt>
            <dd className="mt-1 text-sm text-zinc-900">{syncJob.error_message ?? "-"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
