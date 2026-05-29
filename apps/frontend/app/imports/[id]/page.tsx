import ImportErrorsClient from "./ImportErrorsClient";

type ImportErrorsPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function ImportErrorsPage({ params }: ImportErrorsPageProps) {
  const { id } = await params;

  return <ImportErrorsClient importBatchId={id} />;
}
