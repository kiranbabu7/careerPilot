"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { GOOGLE_CLIENT_ID } from "@/lib/config";

interface GoogleSignInButtonProps {
  onCredential: (idToken: string) => void | Promise<void>;
  onError?: (message: string) => void;
  disabled?: boolean;
}

const SCRIPT_ID = "google-gsi-client";
const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

function loadGoogleScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }

    const existing = document.getElementById(SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("Failed to load Google Sign-In")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Sign-In"));
    document.body.appendChild(script);
  });
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

export function GoogleSignInButton({
  onCredential,
  onError,
  disabled = false,
}: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);
  const onErrorRef = useRef(onError);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  onCredentialRef.current = onCredential;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || disabled) {
      return;
    }

    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google?.accounts?.id) {
          return;
        }

        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => {
            if (response.credential) {
              void onCredentialRef.current(response.credential);
              return;
            }
            onErrorRef.current?.("Google sign-in did not return a credential.");
          },
        });

        containerRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(containerRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          width: Math.min(containerRef.current.offsetWidth || 384, 400),
        });
        setReady(true);
      })
      .catch((error) => {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to initialize Google Sign-In";
        setLoadError(message);
        onErrorRef.current?.(message);
      });

    return () => {
      cancelled = true;
    };
  }, [disabled]);

  if (!GOOGLE_CLIENT_ID) {
    return (
      <div className="space-y-2">
        <Button variant="outline" className="w-full" disabled type="button">
          <GoogleIcon />
          Continue with Google
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Set <code className="text-foreground">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code>{" "}
          and <code className="text-foreground">GOOGLE_OAUTH_CLIENT_ID</code> to
          enable Google sign-in.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-2">
      {!ready && !loadError ? (
        <Button variant="outline" className="w-full" disabled type="button">
          <GoogleIcon />
          Loading Google sign-in...
        </Button>
      ) : null}
      {loadError ? (
        <p className="text-center text-sm text-destructive">{loadError}</p>
      ) : null}
      <div
        ref={containerRef}
        className={`flex w-full justify-center [&>div]:w-full ${ready ? "" : "sr-only"}`}
      />
    </div>
  );
}
