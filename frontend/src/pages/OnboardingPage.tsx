import { useEffect, useState, type ChangeEvent } from "react";
import { ArrowRight, Check, FileSpreadsheet, Link2, Loader2, Store, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { completeOnboarding, connectIntegration, getCatalogProducts, importCatalog } from "../services/api";
import { Badge, Button, GlassCard, SectionTitle, ToastStack, useToasts } from "../components/ui";

type Platform = "shopify" | "woocommerce" | "amazon";

const platforms: Array<{ id: Platform; name: string; description: string }> = [
  { id: "shopify", name: "Shopify", description: "Connect a verified Shopify store domain." },
  { id: "woocommerce", name: "WooCommerce", description: "Connect a verified WooCommerce store domain." },
  { id: "amazon", name: "Amazon", description: "Connect a verified Amazon marketplace domain." },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { toasts, push, dismiss } = useToasts();
  const [file, setFile] = useState<File | null>(null);
  const [platform, setPlatform] = useState<Platform>("shopify");
  const [domain, setDomain] = useState("");
  const [catalogCount, setCatalogCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  useEffect(() => {
    void getCatalogProducts()
      .then((products) => setCatalogCount(products.length))
      .catch(() => setCatalogCount(0))
      .finally(() => setLoadingCatalog(false));
  }, []);

  const selectFile = (event: ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0] || null;
    if (next && !/\.(csv|xlsx)$/i.test(next.name)) {
      setFile(null);
      push("Choose a CSV or XLSX catalog file.", "error");
      return;
    }
    setFile(next);
  };

  const finishOnboarding = async () => {
    if (!file && !domain.trim()) {
      push("Upload a catalog or enter a verified store domain to continue.", "error");
      return;
    }
    setBusy(true);
    try {
      if (file) {
        const result = await importCatalog(file);
        push(`${result.importedCount} catalog records imported.`, "success");
      } else {
        await connectIntegration(platform, domain.trim());
        push(`${platform} connection saved.`, "success");
      }
      await completeOnboarding();
      window.location.assign("/dashboard");
    } catch (error) {
      push(error instanceof Error ? error.message : "Onboarding could not be completed.", "error");
    } finally {
      setBusy(false);
    }
  };

  return <div className="page-stack"><ToastStack toasts={toasts} dismiss={dismiss} /><header className="page-header compact-header"><div><p className="eyebrow">Workspace onboarding</p><h1>Connect your <em>pricing signal.</em></h1><p className="page-lede">Start with a real catalog upload or a verified store connection. No sample products are created automatically.</p></div><Badge tone="indigo" dot>{loadingCatalog ? "Checking catalog" : catalogCount ? `${catalogCount} live products` : "No catalog yet"}</Badge></header><section className="settings-grid"><GlassCard><div className="card-heading"><SectionTitle eyebrow="Option one" title="Upload a catalog" description="Use a CSV or XLSX file with at least name and current_price columns." /><FileSpreadsheet size={18} className="text-indigo" /></div><label className="upload-dropzone"><UploadCloud size={22} /><strong>{file ? file.name : "Choose CSV or XLSX"}</strong><small>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : "Catalog values are validated and persisted to your workspace."}</small><input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={selectFile} /></label>{file && <div className="webhook-note"><Check size={15} /><span>Ready to import this catalog into the authenticated workspace.</span></div>}</GlassCard><GlassCard><div className="card-heading"><SectionTitle eyebrow="Option two" title="Connect a store" description="Persist a verified domain now; catalog sync remains provider-backed and never fabricated." /><Store size={18} className="text-emerald" /></div><div className="platform-picker">{platforms.map((item) => <button type="button" key={item.id} className={`platform-option ${platform === item.id ? "active" : ""}`} onClick={() => setPlatform(item.id)}><span>{item.name}</span><small>{item.description}</small></button>)}</div><label className="field"><span>Verified store domain</span><div className="field-input"><Link2 size={15} /><input value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="store.example.com" /></div></label></GlassCard></section><GlassCard className="onboarding-actions"><div><p className="eyebrow">Ready when you are</p><h2>Bring your first live signal into Klypup.</h2><p>Complete onboarding to unlock catalog intelligence, recommendations, and agent observability.</p></div><Button onClick={() => void finishOnboarding()} disabled={busy}>{busy ? <><Loader2 className="spin" size={15} /> Connecting…</> : <>Complete onboarding <ArrowRight size={15} /></>}</Button></GlassCard></div>;
}
