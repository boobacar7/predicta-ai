"use client";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { safeNextPath } from "@/data/http/auth";
import { useAuthSession } from "@/features/auth/session-context";
import { isDataSourceError } from "@/lib/api/errors";
import { getConfig } from "@/lib/config";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

export function LoginView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status, login } = useAuthSession();
  const config = getConfig();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const nextPath = safeNextPath(searchParams.get("next"));
  const apiReady = Boolean(config.apiBaseUrl);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiReady) return;
    setPending(true);
    setError(null);
    try {
      await login(email, password);
      router.replace(nextPath);
    } catch (caught) {
      setError(
        isDataSourceError(caught)
          ? (caught.message ?? "Connexion refusée.")
          : "Connexion refusée.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center">
      <Card>
        <CardHeader>
          <CardTitle>Accès Private Beta</CardTitle>
          <CardDescription>
            Invitation uniquement. Les probabilités du modèle ne sont jamais des garanties.
          </CardDescription>
        </CardHeader>
        <CardBody>
          {status === "bypassed" ? (
            <p className="text-sm text-muted">
              AUTH_BYPASS est actif sur l’API locale. Les pages produit restent accessibles sans
              session.
            </p>
          ) : null}
          {!apiReady ? (
            <p className="text-sm text-muted">
              Prototype mock local : aucune API n’est configurée, donc aucune session n’est
              nécessaire.
            </p>
          ) : (
            <form className="space-y-4" onSubmit={onSubmit}>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Email invité</span>
                <Input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted">Mot de passe</span>
                <Input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              {error ? (
                <p role="alert" className="text-sm text-risk">
                  {error}
                </p>
              ) : null}
              <Button type="submit" variant="primary" className="w-full" disabled={pending}>
                {pending ? "Connexion…" : "Se connecter"}
              </Button>
            </form>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
