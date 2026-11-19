# Early Radar — kritik baxış və icra (2026-11-19)

**Sual (owner):** 10x–100x aralığında rug/scam olmadan satmaq üçün nəyə baxmalıyıq?
DexScreener-də SOL token-lərin çoxu qalxır, onları vaxtında necə tapaq?

**Əhatə:**
- bu sənədin analizi (kod və canlı DexScreener məlumatı);
- [SWOT və defekt auditi](SWOT_AND_DEFECT_AUDIT_2026-11-11.md);
- [Ultra-Early səhifə auditi](ULTRA_EARLY_PAGE_AUDIT_2026-11-12.md).

> Codex SWOT faylı [`CODEX_SWOT_2026-11-19.md`](CODEX_SWOT_2026-11-19.md)
> repoya əlavə olundu (commit `1ab57d2`) və §6-da bu sənədlə birləşdirildi.

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
8. **Holder konsentrasiyası** (`holder_concentration.py`, `SolanaRpcAdapter.fetch_holder_snapshot`).
   Revival alert namizədi üçün ən böyük 20 token hesabı oxunur. Hesablar sahibə görə toplanır. Pool və ya curve hesabı (DexScreener pair ünvanı) holder sayılmır.
   - top10 ≥ 50% və ya top1 ≥ 15% olarsa risk `HIGH`-dır və alert göndərilmir. Siqnal isə səbəb kodu ilə yazılır.
   - Mənbə əlçatmazdırsa, alert göndərilir, amma mətndə "Holder concentration: UNKNOWN" yazılır. UNKNOWN heç vaxt "paylanmış" kimi şərh olunmur.
   - Sahibi oxunmayan hesab holder sayılır (konservativ yanaşma).

   **Məhdudiyyət:** publicnode `getTokenLargestAccounts`-ı token olmadan rədd edir. mainnet-beta isə bu metod üçün 429 qaytarır (2026-11-19, bu sessiyanın IP-si). Real dəyər almaq üçün `SOLANA_RPC_URL`-də açarlı RPC lazımdır (məs. Helius free tier).

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
4. **Insider sübutu.** Creator və bundle cüzdanlarının satışı çıxış triggeri kimi istifadə olunsun. Holder konsentrasiyası §3.8-də edilib; açarlı RPC ilə canlı yoxlama gözləyir.
5. **Forward collector-un miqyaslanması (C7).** Lifecycle outcome-ları təsdiqlənəndən sonra collector ya batch-ə keçirilsin, ya da ləğv edilsin.
6. **Web.** Ultra-Early səhifəsinə lifecycle siqnalları və manual pozisiyalar paneli.
7. **Narrativ klasterləmə** (məs. 2026-11-19-da Çin adlı meme klasteri).

## 6. Codex SWOT ilə birləşdirmə (2026-11-19)

Codex auditi `6862d1e` commit-inə aiddir, yəni lifecycle watch-dan əvvəlki vəziyyətə.
Hər bəndi kodda və ya canlı məlumatda yenidən yoxladım:
- "✔ düzəldildi" — bu checkpoint-də kod dəyişib;
- "✔ təsdiq" — tapıntı yoxlanıldı və doğru çıxdı;
- "→" — sonraya qalır.

### 6.1 Ortaq nəticə

Hər iki analiz eyni əsas boşluğu göstərir.
- **Codex:** "Pump.fun və PumpSwap əməliyyatlarını eyni mint üzrə bütöv izləmək". Bundan əlavə, ölçüyə uyğun giriş və çıxış sübutu tələb edir: mark zirvəsi, satışa uyğun zirvə və realizə olunmuş nəticə ayrı göstəricilərdir.
- **Bu baxış:** radar ilk 15 dəqiqədən sonra kordur (C1–C4).

Lifecycle watch və exit advisor (§3) birinci tələbi DexScreener aqreqatları ilə qismən bağlayır. Codex-in ikinci tələbi — ölçüyə uyğun satış nəticəsi — hələ açıqdır. Outcome label-ları indi bunu açıq yazır: `outcome_semantics: MARK_MARKET_CAP`, `sellable_peak_multiple` və `realized_multiple` isə `null`-dır.

### 6.2 Codex-in "Cari checkout-da prioritet məsələlər" bölməsi

| # | Codex tapıntısı | Yoxlama | Vəziyyət |
| --- | --- | --- | --- |
| 1 | Pump IDL drift: rəsmi `639b87f`-də 47 deyil, 56 instruction var (`buy_v3`, `sell_v3`, `buy_exact_quote_in_v3`, `multi_hop_curve_swap`). | ✔ təsdiq: diff yenidən hesablandı, 9 yeni instruction var. Codex qeyd etməyib, amma `TradeEvent`-in sonuna `creator_fee_unclaimed` sahəsi əlavə olunub. 30 finalized mainnet tranzaksiyasında Pump kontekstindəki 27 trade instruction-ın (`BuyExactQuoteInV3` və `SellV3` daxil) hər biri tam bir `TradeEvent` kimi decode olundu, uyğunsuzluq 0. Yəni v3 trade tape-dən **itmir**. | ✔ düzəldildi: `PUMP_FUN_UNROUTED_INSTRUCTIONS` (routing `TODO_VERIFY`, tape coverage təsdiqlənib), mainnet fixture `pump_fun_v3_trades_mainnet.json`, regressiya testi, `scripts/pump_idl_drift.py` doktoru. → v3 instruction-larının account layout-unu yoxlayıb routing etmək; qeyri-SOL quote mint-lərini (`quote_mint` sahəsi) decode etmək. |
| 2 | DEX lead-time ölçmə xətası: ilk müsbət cavab vaxtı kimi dövrün başlanğıcı (`query_now`) yazılır; 429 və timeout `NO_PAIR` sayılmamalıdır. | ✔ təsdiq. Əlavə tapıntı: DexScreener-in uğurlu, amma boş cavabı `REQUEST_FAILED` sayılırdı, yəni əksinə səhv. | ✔ düzəldildi: hər sorğu üçün `dex_query_started_at` və `dex_query_responded_at`; ilk görünmə interval kimi (`dex_first_seen_lower_bound_at` – `upper_bound_at`), ilk sorğu müsbətdirsə `UPPER_BOUND_ONLY`; `DexScreenerNoPairError` → `NO_PAIR_YET`; `TIMEOUT` ayrıca status. → Müstəqil mint inventarı və DEX boost-un ayrıca qeydi. |
| 3 | Jupiter `order()` yolunda `priceImpact` faiz kimi gəlir, kod onu fraksiya kimi çevirir (1% → 10 000 bps); $50 testi üçün xalis round-trip nəticəsi və ayrı səbəb kodları lazımdır. | ✔ təsdiq (canlı `/swap/v2/order` cavabı: `priceImpact=-0.0307`, `priceImpactPct=-0.000307`). Əlavə tapıntı: mənfi (qiymətin xeyrinə olan) impact etibarlı quote-u `ProviderSchemaError` ilə rədd edirdi. | ✔ düzəldildi: fraksiya sahəsinə üstünlük verilir, faiz sahəsi ÷100 ilə çevrilir, mənfi impact 0 sayılır. Depth probe ayrıca statuslar qaytarır: `DEPTH_RATE_LIMITED`, `NO_ROUTE`, `PROVIDER_TIMEOUT`, `QUOTE_STALE`, `IMPACT_TOO_HIGH`, `ROUND_TRIP_LOSS_TOO_HIGH`, `SOL_REFERENCE_UNAVAILABLE`, `PROVEN` və s. Xalis round-trip nisbəti hesablanır; 0.80-dən aşağı olarsa likvidlik sübutu yoxdur (hipotez). |
| 4 | Forward collector: dövrdə 16 launch, bütün sətirləri oxuyur, ardıcıl sorğular. `STATISTICAL_SAMPLE_SUFFICIENT` sətirləri sayır, unikal mint-ləri yox. | ✔ təsdiq (həm də bu baxışın C7 bəndi). | ✔ düzəldildi: kifayətlik hər horizon üçün unikal mint sayına görə yoxlanır (`OUTCOME_UNIQUE_MINTS_BY_HORIZON`). Lifecycle watch inkremental cursor və batch ilə işləyir. → Collector-u batch-ə keçirmək; creator/cluster üzrə unikal saylar və etibar intervalları. |
| 5 | `ConvexExitEvaluator` siyasətə uyğun `candidate_exits` tapmayanda eyni trade nəticəsini hər siyasət üçün təkrar istifadə edir, nəticədə sıralama süni olur. CLI faylın mövcudluğuna görə `HISTORICAL_REAL` etiketi verir. | ✔ təsdiq. | ✔ düzəldildi: öz simulyasiya olunmuş çıxışı olmayan siyasət sıralanmır (`selection_objective=None`, `CONVEX_EXIT_POLICY_OUTCOMES_MISSING`). Heç birinin çıxışı yoxdursa status `INSUFFICIENT_POLICY_OUTCOMES` olur. CLI etiketi dataset-in elan etdiyi `evidence_class`-dan götürülür; elan yoxdursa `UNDECLARED`. → Hər siyasət üçün fill sətirləri və PumpSwap SDK ilə sell math. |

### 6.3 Codex-in açıq repo tövsiyələri

Heç bir upstream kod kopyalanmayıb. Bütün düzəlişlər müstəqil yazılıb, AGENTS.md-dəki lisenziya qaydasına uyğun.

- **Sonraya qalır (P0):**
  - `shaurya35/solana-realtime-indexer` (MIT) — golden fixture və event-ID müqayisəsi metodu;
  - `dynamolabs/launchpad-registry` (kod MIT, data CC0) — LaunchLab və Meteora DBC identikliyi üçün offline diff;
  - `launchtape-io/pump-fun-backtest` (kod MIT; data lisenziyası ayrıdır, istifadədən əvvəl yoxlanmalıdır) — fill modelinin müqayisəsi.
- **Sonra:** P1/P2 mənbələri (sol-parser-sdk, carbon, jetstreamer, CMU Meme Coin Factories, red2400, PumpScope, solana-launch-study).
- **Ehtiyatla:** MELT CC BY-NC 4.0 lisenziyalıdır, kommersiya istifadəsi üçün ayrıca icazə lazımdır.

### 6.4 Birləşdirilmiş növbəti addımlar

Codex-in "İlk tətbiq sırası" və §5 bir siyahıda birləşdirilib:

1. **Pump.fun → PumpSwap əhatəsi on-chain.** `migrate`/`CompleteEvent` və PumpSwap trade-ləri; v3 routing-in yoxlanması (6.2-1, §5-2, §5-3).
2. **Ölçüyə uyğun satış nəticəsi.** Lifecycle outcome-larına `sellable_peak` və `realized` sahələri; manual pozisiya üçün çıxış quote-ları (6.1, Codex mərhələ 3).
3. **Müstəqil kohort və kalibrasiya.** Unikal mint/creator sayları, TRAIN/VALIDATION/TEST bölgüsü, creator ailəsinin hissələr arasında sızmasının yoxlanması (Codex mərhələ 5, §5-1).
4. **Holder və insider sübutu açarlı RPC ilə** (§3.8).
5. **Əlavə launchpad.** LaunchLab və ya Meteora DBC — hansı daha çox ölçülə bilən fürsət buraxdırırsa (Codex addım 4).
6. **Rust sidecar** yalnız ölçülmüş gecikmə qazancı ilə (Codex).

Codex-in rəqəmlə göstərdiyi vacib qayda: 100× chart sayı strategiyanın xalis nəticəsi deyil. Məsələn, 100 bərabər girişdən biri bütün həcmi ilə 100× satılsa və qalan 99-u tam itsə, nəticə başabaşdır. Exit advisor-un pilləli satışı və outcome semantikası bu qaydaya uyğundur.
