# Early Radar — kritik baxış və icra (2026-11-19)

**Sual (owner):** 10x–100x aralığında rug/scam olmadan satmaq üçün nəyə baxmalıyıq?
DexScreener-də SOL token-lərin çoxu qalxır, onları vaxtında necə tapaq?

**Əhatə:**
- bu sənədin analizi (kod və canlı DexScreener məlumatı);
- [SWOT və defekt auditi](SWOT_AND_DEFECT_AUDIT_2026-11-11.md);
- [Ultra-Early səhifə auditi](ULTRA_EARLY_PAGE_AUDIT_2026-11-12.md).

> **Codex SWOT faylı (`MemeRadar-SWOT-ve-repo-arasdirmasi.md`) bu sessiyada
> əlçatan deyil.** Fayl owner-in lokal maşınındadır (`/home/ubra/...`) və repoya
> push olunmayıb. Bulud sessiyasına isə kompüter qovluğu qoşulmayıb. Fayl
> `docs/audits/` altına commit olunanda bu sənədin §6 cədvəli onunla
> birləşdiriləcək. Bu bənd yalnız həmin girişin olmamasına görə `BLOCKED`-dir.

## 1. Əsas tapıntı: radar yanlış pəncərəyə baxırdı (P0)

| # | Tapıntı | Sübut |
| --- | --- | --- |
| C1 | Early radar token-i yalnız launch-dan sonrakı 30…900 s ərzində qiymətləndirir. Trade tape 20 dəqiqə saxlanır, sonra token unudulur. | `pumpfun_forward.py:44` `EARLY_REEVALUATION_OFFSETS_SECONDS`, `solana_raw_stream.py` `trade_tracking_window=20m` |
| C2 | Graduation (`migrate`) decode olunur, amma heç bir istehlakçı onu istifadə etmir. Stream tranzaksiyanı yalnız `Create` loglarına görə çəkir, ona görə migrate sətirləri bazaya düşmür. | `solana_raw_stream.py:286`, `early_discovery.py` |
| C3 | 2026-11-19-da canlı DexScreener snapshot-ı götürüldü (44 Solana token, boost/profile siyahısı). Ən çox qalxanların hamısı graduate olub PumpSwap-a keçmiş, 10–35 saatlıq pair-lərdir: LuckyCoin +1607%, AIB +698%, NOBUSHIBA +386%. 1–18 saatlıq bir çox PumpSwap pair-i isə −80…−95% düşüb. | scratchpad snapshot; nümunə qərəzlidir (pullu boost siyahısı) |
| C4 | Eyni gün AIB-in market cap-i $440k-dan $1.8k-a düşdü. "Qalxdı, sonra çökdü" yolu tipikdir. Sistemdə manual pozisiya üçün **heç bir satış/çıxış alerti yox idi.** | canlı yenidən oxunuş |
| C5 | Telegram outbox `CandidateStateChanged`-dən başqa hadisələri (`ExitSignal`, `RiskEscalation`, …) səssizcə atırdı. | `operations_jobs._handle_alert_event` |
| C6 | **Bug:** DexScreener `priceChange` mənfi olduqda `None` (UNKNOWN) oxunurdu. Səbəb: mənfi dəyərləri rədd edən parser həmin sahə üçün də istifadə olunurdu. Nəticədə hər düşüş görünməz idi. | `dexscreener._parse_price_change` (düzəldildi, test var) |
| C7 | Forward evidence collector hər dövrdə bütün research sətirlərini yükləyir. Bir dövrdə 16 launch emal edir, hər mint üçün ayrıca sorğu atır və köhnələrdən başlayır. Saatda ~500 launch axınında `1h` offset-i saatlarla gec götürülə bilər. | `forward_evidence._load_rows`, `_MAX_LAUNCHES_PER_CYCLE=16` |

## 2. Fazalar üzrə model: nəyə baxmalı

| Faza | Vaxt | Baxılacaq siqnal | İndi |
| --- | --- | --- | --- |
| A. Launch | 0–15 dəq | bundle və sniper payı, dev alışı, deployer tarixçəsi, orqanik alıcılar | early radar (mövcud) |
| B. Curve | 15 dəq → graduation | curve-də sürətlənən həcm, alıcı/satıcı balansı, market cap $15k+ | **lifecycle watch (yeni)** |
| C. Graduation | migrate ± 1 saat | dump-dan sonra dəstəyin saxlanması | **lifecycle watch, venue keçidi (yeni)**; zəncir əsaslı migrate sübutu sonrakı iş |
| D. İkinci dalğa | 1–72 saat | həcm sürətlənməsi (5 dəq / saatlıq baza), alış sayı, B/S nisbəti, m5 və h1 qiymət artımı, ardıcıl iki nümunə | **REVIVAL_WATCH (yeni)** |
| Çıxış | alışdan sonra | 2x-də ilkin məbləği çıxarmaq, pilləli satış, trailing stop, hard stop, likvidlik çöküşü, paylama (dump) təzyiqi, köhnə məlumat | **MANUAL_EXIT (yeni)** |

## 3. Bu checkpoint-də icra olunanlar

1. **`lifecycle_watch.py`** (application, saf funksiyalar):
   - venue normallaşdırılması: `PUMPFUN`, `PUMP.FUN`, `pumpfun` eyni venue sayılır (Ultra-Early auditinin B6 bəndi);
   - HOT/WARM/COLD/RETIRED polling tier-ləri;
   - sustained revival detektoru: bütün kriteriyalar iki ardıcıl nümunədə, ən azı 60 s fərqlə ödənməlidir; cooldown 6 saat;
   - lookahead olmadan outcome label-ları (1h, 6h, 24h, 72h): `PEAK_2X`, `PEAK_10X`, `PEAK_100X`, `COLLAPSED`, `FLAT`, `UNKNOWN`. Hər label-da resolution (`COARSE`/`FINE`) və `config_hash` qeyd olunur.
2. **`manual_exit.py`** — manual pozisiya üçün çıxış məsləhətləri:
   - pilləli satış: 2x-də 50%, sonra 5x, 10x, 25x, 50x, 100x;
   - trailing stop: 3x-dən sonra zirvədən 35% geri çəkilmə;
   - hard stop: ilkin məbləğ çıxarılmayıbsa 0.5x;
   - likvidlik ≥50% düşərsə xəbərdarlıq;
   - dump təzyiqi: satışlar alışların ≥2 qatı və 5 dəqiqədə qiymət ≤−20%;
   - köhnə məlumat: 3 dəqiqə.

   Entry qiyməti operator-un real fill-idir (`OPERATOR_EXECUTED`). Fill verilməyibsa, qeyd anındakı market qiyməti götürülür (`MARKET_REFERENCE_AT_REGISTRATION`). Bu iki semantika heç vaxt bir-birinin yerinə işlənmir.
3. **DexScreener batch adapteri:** `tokens/v1` bir sorğuda 30 mint qaytarır. Cavabda olmayan mint `None` (UNKNOWN) sayılır, sıfır deyil. Fixture real mainnet cavabıdır.
4. **`LifecycleWatchWorker`:**
   - launch-lar `ingested_at` cursor-u ilə inkremental oxunur;
   - bir dövrdə ən çox 20 sorğu;
   - 429 alanda dövr dayanır və bu, "missing" sayılmır;
   - DexScreener-də hələ index olunmamış yeni mint-lər üçün grace dövrü var;
   - restart-dan sonra outcome və exit-advice dedupe-u saxlanır.

   Revival alerti üç şərtlə göndərilir:
   - launch safety PASS və ya CAUTION;
   - mint və freeze authority revoked (revoke daimidir);
   - heç bir hard block yoxdur.

   Safety məlumatı yoxdursa, siqnal yazılır, amma alert göndərilmir (fail-closed).
5. **Telegram əmrləri** (yalnız konfiqurasiya olunmuş operator chat-i qəbul olunur; mesaj mətni saxlanmır):
   - `/bought <mint> [entry_price_usd] [size_usd]`;
   - `/sold <mint>`;
   - `/positions`;
   - `/help`.
6. **Alert çatdırılması:** yeni `REVIVAL_WATCH` və `MANUAL_EXIT` tipləri; 10 dəqiqəlik təravət pəncərəsi. Renderer mesaja bu qeydləri əlavə edir: "WATCH EVIDENCE ONLY - NOT ENTRY_READY" və "ADVISORY ONLY - YOU EXECUTE MANUALLY".
7. **Bug fix:** imzalı `priceChange` (C6).

Konfiqurasiya: `LIFECYCLE_WATCH_ENABLED=true` (açarsız DexScreener). Qorunan
rejimlər dəyişməyib.

## 4. Ehtimal və risk (dürüst hesab)

- Bütün hədlər (`LifecyclePolicy`, `ExitPolicy`) kalibrasiya olunmamış
  hipotezlərdir. Versiyalanıblar və `config_hash`-ları var.
- $50-lıq bərabər mərclərlə nümunə: qələbə ehtimalı 30%, qələbədə orta çıxış 3x, məğlubiyyətdə itki 80% olsun. Onda EV ≈ +0.04/$ olur. Bu qədər nazik gözlənti dəqiqliyin bir neçə faiz düşməsi ilə mənfiyə çevrilir. Real qazancı nadir 10x–100x quyruğu gətirir. Bu səbəbdən:
  - çıxış qaydası mütləqdir;
  - hansı siqnalın işlədiyini **outcome label-ları ilə ölçmək** lazımdır.
- REVIVAL_WATCH token-ləri həm də ən çox dump olunan populyasiyadır (C3/C4).
  Çatışmayan sübutlar alert mətnində açıq yazılır:
  - holder konsentrasiyası;
  - insider paylaması;
  - deployer çıxışları.

## 5. Növbəti addımlar (prioritet sırası ilə)

1. **Kalibrasiya.** 1–2 həftəlik `lifecycle.outcome` məlumatından sonra T anındakı xüsusiyyətlər 10x və rug ilə müqayisə edilsin. Embargo/no-lookahead split mövcud `calibration.py`-da var.
2. **Zəncir əsaslı graduation.** Pump `CompleteEvent` / `migrate` logları stream-də decode olunsun (C2). Bunun üçün əvvəlcə discriminator mainnet fixture ilə yoxlanmalıdır (`TODO_VERIFY`).
3. **PumpSwap tape.** Graduation-dan sonra on-chain trade-lər decode olunsun ki, revival DexScreener aqreqatlarından asılı qalmasın. Bunun üçün PumpSwap program ID-si və event layout-u yoxlanmalıdır.
4. **Holder və insider sübutu.** `getTokenLargestAccounts` ilə top10 konsentrasiyası, həmçinin creator və bundle cüzdanlarının satışı (çıxış triggeri kimi).
5. **Forward collector-un miqyaslanması (C7).** Lifecycle outcome-ları təsdiqlənəndən sonra collector ya batch-ə keçirilsin, ya da ləğv edilsin.
6. **Web.** Ultra-Early səhifəsinə lifecycle siqnalları və manual pozisiyalar paneli.
7. **Narrativ klasterləmə** (məs. 2026-11-19-da Çin adlı meme klasteri).

## 6. Codex SWOT ilə birləşdirmə

`BLOCKED`: fayl repoya əlavə olunmayıb (yuxarıdakı qeydə bax).
