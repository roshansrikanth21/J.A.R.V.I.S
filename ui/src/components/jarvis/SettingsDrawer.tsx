import { useEffect, useState } from "react";
import { Settings, Volume2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Panel } from "./Panel";

interface VoiceSettings {
  input_device_index: number | null;
  enable_clap_wake: boolean;
  enable_keyword_wake: boolean;
  clap_threshold: number;
  clap_count_required: number;
  clap_window_s: number;
  clap_cooldown_s: number;
}

interface AudioDevice {
  index: number;
  name: string;
}

export function SettingsDrawer() {
  const [settings, setSettings] = useState<VoiceSettings | null>(null);
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const [settingsRes, devicesRes] = await Promise.all([
          fetch("/api/settings/voice"),
          fetch("/api/audio/devices"),
        ]);
        
        if (settingsRes.ok) {
          const data = await settingsRes.json();
          setSettings(data.settings);
        }
        
        if (devicesRes.ok) {
          const data = await devicesRes.json();
          // Assuming api returns { devices: [...] } where items are either strings or objects with index
          // We'll normalize to an array of { index, name }
          const devs = data.devices.map((d: any, idx: number) => {
            if (typeof d === "string") return { index: idx, name: d };
            return { index: d.index ?? idx, name: d.name ?? d.toString() };
          });
          setDevices(devs);
        }
      } catch (err) {
        console.error("Failed to load settings:", err);
      }
    }
    loadData();
  }, []);

  const updateSetting = async (key: keyof VoiceSettings, value: any) => {
    if (!settings) return;
    const nextSettings = { ...settings, [key]: value };
    setSettings(nextSettings);
    
    setSaving(true);
    try {
      await fetch("/api/settings/voice", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextSettings),
      });
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet>
      <SheetTrigger asChild>
        <button className="icon-button" title="System Settings">
          <Settings className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent className="w-[400px] sm:w-[540px] bg-background border-line text-foreground overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="text-hud font-mono tracking-widest uppercase">System Config</SheetTitle>
          <SheetDescription className="text-muted-foreground tracking-wider uppercase text-xs">
            Adjust core JARVIS parameters
          </SheetDescription>
        </SheetHeader>

        {settings ? (
          <div className="space-y-6">
            <Panel title="Wake Detection" status={saving ? "saving" : "online"} className="bg-background">
              <div className="space-y-5">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-xs uppercase tracking-widest text-foreground">Keyword Wake</Label>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Trigger via 'Hey Jarvis'</p>
                  </div>
                  <Switch 
                    checked={settings.enable_keyword_wake}
                    onCheckedChange={(v) => updateSetting("enable_keyword_wake", v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-xs uppercase tracking-widest text-foreground">Clap Wake</Label>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Trigger via clap pattern</p>
                  </div>
                  <Switch 
                    checked={settings.enable_clap_wake}
                    onCheckedChange={(v) => updateSetting("enable_clap_wake", v)}
                  />
                </div>
              </div>
            </Panel>

            <Panel title="Clap Threshold Tuning" className="bg-background">
              <div className="space-y-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs uppercase tracking-widest text-foreground">Threshold ({settings.clap_threshold})</Label>
                  </div>
                  <Slider 
                    value={[settings.clap_threshold]} 
                    min={1000} 
                    max={30000} 
                    step={500}
                    onValueChange={(vals) => updateSetting("clap_threshold", vals[0])}
                  />
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider text-right">
                    Lower to increase sensitivity
                  </p>
                </div>
              </div>
            </Panel>

            <Panel title="Audio Hardware" className="bg-background">
              <div className="space-y-3">
                <Label className="text-xs uppercase tracking-widest text-foreground">Input Device</Label>
                <Select 
                  value={settings.input_device_index?.toString() ?? "default"}
                  onValueChange={(v) => {
                    const idx = v === "default" ? null : parseInt(v, 10);
                    updateSetting("input_device_index", idx);
                  }}
                >
                  <SelectTrigger className="w-full font-mono text-xs border-line bg-panel uppercase tracking-wider">
                    <Volume2 className="h-4 w-4 mr-2 text-hud" />
                    <SelectValue placeholder="Default Audio Device" />
                  </SelectTrigger>
                  <SelectContent className="bg-panel border-line font-mono text-xs uppercase tracking-wider">
                    <SelectItem value="default">Default Device</SelectItem>
                    {devices.map((d) => (
                      <SelectItem key={d.index} value={d.index.toString()}>
                        {d.index}: {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </Panel>
          </div>
        ) : (
          <div className="text-center py-10 text-muted-foreground font-mono text-xs uppercase tracking-widest animate-pulse">
            Fetching telemetry...
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
