import SyncJobDetailClient from "./SyncJobDetailClient";

type SyncJobDetailPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function SyncJobDetailPage({ params }: SyncJobDetailPageProps) {
  const { id } = await params;

  return <SyncJobDetailClient syncJobId={id} />;
}
