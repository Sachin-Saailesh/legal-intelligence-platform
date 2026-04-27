"use client";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";
import { useRouter } from "next/navigation";

function QueryRedirectInner() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const session = searchParams.get("session");
  const router = useRouter();
  useEffect(() => {
    const url = `/matters/${id}?tab=query${session ? `&session=${session}` : ""}`;
    router.replace(url);
  }, [id, session, router]);
  return null;
}

export default function QueryRedirect() {
  return (
    <Suspense>
      <QueryRedirectInner />
    </Suspense>
  );
}
