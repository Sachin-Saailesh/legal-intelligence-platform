"use client";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DocumentsRedirect() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => { router.replace(`/matters/${id}?tab=documents`); }, [id, router]);
  return null;
}
