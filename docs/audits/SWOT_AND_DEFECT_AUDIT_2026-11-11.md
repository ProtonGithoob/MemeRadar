# MemeRadar — SWOT və defekt auditi (2026-11-11)

**Əhatə:** `claude/exciting-brahmagupta-0k7pds` budağı, HEAD `bea5c4e` ("before claude"), təmiz GitHub klonu.
Operatorun lokal qovluğu (`/home/ubra/codex/MemeRadar`) bu sessiyadan əlçatan olmayıb. Ona görə
`artifacts/verification/`, lokal `.venv` və Docker konteynerləri yoxlanmayıb. Bütün yollar repo köküne nisbidir.

**Metod:**
- Təmiz bootstrap edildi (`requirements.lock` və `npm ci`). Bütün lokal gate-lər işlədildi.
- Dörd müstəqil kod auditi aparıldı:
  1. qərar/risk/scoring;
  2. stream/provayder/worker;
  3. paper/exit/backtest (kvant baxışı);
  4. API/persistence/infra/web.
- Hər P0 iddiası və ən kritik P1 iddiaları kodda əl ilə təsdiqləndi. Üç tapıntı skriptlə reproduksiya olundu.
- Heç bir istehsal koduna dəyişiklik edilmədi. Bu sənəd yalnız hesabatdır.

---

## 0. İcra xülasəsi (verdikt)

MemeRadar mühəndislik baxımından **çox intizamlı skeletdir**. Bunu göstərənlər:
- provider-müstəqil portlar;
- fail-closed semantikası;
- `(program_id, discriminator)` ilə routing;
- reason code-lar;
- live/paper rejimlərinin ayrılması;
- 1650 backend + 86 frontend test.

Lakin layihənin **əsas məqsədi** — erkən, rug-dan təmizlənmiş, icra oluna bilən giriş tapmaq və asimmetrik
exit — hazırda üç səviyyədə pozulur:

1. **Data bütövlüyü.** Stream restart və gap-verifikasiya yolları məlumat itkisini "VERIFIED" kimi qəbul edə bilir.
   Bu, "coverage UNKNOWN" vəziyyətini sükutla "coverage OK" vəziyyətinə çevirir.
2. **Tədqiqat etibarlılığı.** Backtest, calibration və feature yollarında lookahead, survivorship və label
   leakage var. İstənilən gələcək "alpha" ölçüsü sistematik olaraq **yuxarı sürüşəcək**.
3. **Paper icra.** Trailing stop və break-even heç vaxt işə düşmür. Quote ala bilməyən (rug olmuş) pozisiyalar
   əbədi OPEN qalır. Nəticədə paper PnL optimist olur.

Bundan əlavə, **ENTRY_READY istehsal yolunda faktiki olaraq əlçatmazdır** (bax §3.1). Sistem hazırda
qərar mühərriki yox, müşahidə/diaqnostika platformasıdır.

**Ehtimal baxımından:** cari kodla toplanan istənilən forward və backtest kohortu yanlış çıxacaq. Səbəb
yuxarıdakı qərəzlərin hamısının eyni istiqamətdə olmasıdır (itkilər çıxarılır, gələcək məlumat daxil
edilir). Hər hansı **real-pul qərarı bu nəticələrə əsaslana bilməz**. Növbəti addım yeni feature deyil,
**ölçmə alətinin düzəldilməsidir**.

---

## 1. Quality gate nəticələri (təmiz klonda, 2026-11-11)

| Gate | Nəticə | Qeyd |
| --- | --- | --- |
| Ruff | PASS | |
| mypy (187 fayl) | PASS | |
| pytest (təmiz `requirements.lock`) | **FAIL** | `ModuleNotFoundError: aiosqlite`. 22 test faylı `sqlite+aiosqlite` istifadə edir, amma paket nə `requirements.lock`, nə də `pyproject.toml`-dadır. |
| pytest (`aiosqlite` lokal əlavə edildikdən sonra) | 1650 passed, 34 deselected | `-n 4` ilə 21 s. |
| Frontend lint / typecheck / vitest | PASS / PASS / 86 passed | |
| `npm audit --omit=dev` | 0 vulnerability | |
| PostgreSQL inteqrasiyası, Playwright, prod build, Trivy | İşlədilmədi | Mühit məhdudiyyəti. |

**Nəticə:** `STATUS.md`-dəki "make verify exited 0" iddiası **təmiz bootstrap-dan reproduksiya olunmur**.
CI (`.github/workflows/ci.yml` yalnız `requirements.lock` quraşdırır) `make test` addımında qırılmalıdır.
Lokal venv-də `aiosqlite` əllə quraşdırılıb.

Lokal yoxlama:

```bash
cd /home/ubra/codex/MemeRadar && grep -ci aiosqlite requirements.lock pyproject.toml
```

---

## 2. SWOT (məqsədə görə)

### Strengths — güclü tərəflər

- **Təhlükəsizlik invariantları kodda məcbur edilir.** Live flag override-ları `Settings`, `PaperExecutionPolicy`,
  `ExitRulePolicy` və `BacktestPolicy`-də exception atır. Env bool parsing sərtdir. MCP serveri həqiqətən
  read-only-dir. Web mutasiya route-u həmişə 403 qaytarır. API konteynerləri non-root işləyir.
- **Protokol identikliyi düzgün qurulub.** Routing həmişə `(program_id, tag)` ilə gedir;
  `route_by_discriminator` discriminator-only routing-i rədd edir.
- **Provider abstraksiyası və fail-closed fəlsəfəsi aydındır.** `UNKNOWN` ilə `0` semantikası sənədləşib
  və əksər yerlərdə tətbiq olunub.
- **Telegram yolu yetkindir.** Token loglara düşmür. Göndərmə retry edilmir. Timeout `DELIVERY_UNKNOWN`
  kimi təsnif olunur.
- **Paper icrada bir neçə şey düzgündür.** Komissiya hər iki ayağa düzgün işarə ilə tətbiq olunur. Alış
  slippage-i adversdir. Portfel exposure və max-positions limitləri var. Quote causality düzəlişi edilib.
- **Test bazası genişdir.** 60k sətir test, contract/property testləri, deterministik replay fixture-ləri.

### Weaknesses — zəif tərəflər

- **Data bütövlüyündə P0 boşluqlar var** (§3.1): restart gap-i, finalized olmayan slotların "skipped" sayılması,
  sticky `reconnect_reason`.
- **Tədqiqat stack-ı qərəzlidir** (§3.2): lookahead, survivorship, embargo-suz split, optimist fill-lər.
- **Paper exit mühərriki yarımçıqdır** (§3.3): high-watermark yenilənmir, zombi pozisiyalar qalır, kill-switch yoxdur.
- **Live ingest arxitekturası dar boğazdır.**
  - WebSocket `recv` döngüsü daxilində ardıcıl `getTransaction` çağırılır (head-of-line blocking).
  - Yalnız launch tranzaksiyaları çəkilir, yəni **live trade tape yoxdur**. Flow və momentum feature-ları
    real vaxtda qidalanmır.
  - Bir əlçatmaz tranzaksiya bütün subscription-u reconnect-ə məcbur edir.
- **Yalnız Pump.fun bonding-curve identikliyi `VERIFIED`-dir.** PumpSwap, Raydium (AMM v4/CPMM/CLMM) və
  Meteora `TODO_VERIFY` vəziyyətindədir. Miqrasiyadan sonrakı mərhələ, yəni 20x–100x-in əsasən baş verdiyi
  yer, autoritativ deyil.
- **Kod çoxdur, wiring azdır.** Bunlar istehsal kodunda heç yerdə instansiya edilmir:
  - Helius stream, Birdeye fallback, GoPlus, Chainlink, RugCheck `assess()`;
  - `SignalHardeningAnalyzer` (yalnız replay-də işləyir);
  - `PaperSizingPolicy`.
- **Sənəd/proses yükü böyükdür.**
  - 31.9k sətir markdown var, kod isə 117k sətirdir.
  - Kökdə 5 ayrı "CODEX prompt" faylı var.
  - `STATUS.md` repoda olmayan `artifacts/` sübutlarına istinad edir.
  - `PRODUCT_ISSUE_GRID_LATEST.md`-də dublikat ID-lər var (P02, P05, P06, P11, P14, P18, P20 iki dəfə).
  - Status sənədi "branch main, dirty" deyir, faktiki vəziyyət isə fərqlidir.

### Opportunities — imkanlar

- **Ölçmə alətini düzəltmək ucuzdur, effekti isə böyükdür.** §3.2-dəki düzəlişlərin əksəriyyəti 10–50 sətirlikdir.
  Bunlardan sonra forward kohort həqiqətən etibarlı olur.
- **Live trade tape.** Mövcud `logsSubscribe`-dan trade notification-ları da emal etmək mümkündür. Bunun
  üçün `getTransaction`-u bounded worker pool-a çıxarmaq və log-parsing ilə yüngül tape qurmaq lazımdır.
  Nəticədə `OrganicFlowAcceleration` və momentum korroborasiyası canlanır.
- **Ödənişli RPC və ya Yellowstone gRPC** public RPC 429 problemini və `getTransaction` N+1 xərcini birdən
  aradan qaldırır. Arxitektura buna hazırdır (portlar mövcuddur).
- **PumpSwap/Raydium identikliyinin verifikasiyası** miqrasiyadan sonrakı fazanı (ən böyük upside) açır.
- **Artıq yazılmış, amma qoşulmamış adapterlər** (RugCheck, GoPlus, Birdeye fallback) risk sübutlarının
  əhatəsini dərhal genişləndirə bilər.

### Threats — təhdidlər

- **Yanlış alpha sübutu ən böyük təhlükədir.** Survivorship və lookahead qərəzləri eyni istiqamətdə toplanır.
  Komanda "edge var" qərarına gəlib canlı pula keçərsə, real nəticə sistematik olaraq daha pis olacaq.
- **Rəqabət gecikməsi.** Pump.fun launch-ları üçün sub-saniyə botları ilə public RPC və ardıcıl
  `getTransaction` arxitekturası rəqabət apara bilmir. "Ultra-early" vədi struktur olaraq risk altındadır.
- **Protokol drift-i.** Pump.fun instruction layout-u dəyişərsə, yalnız tək bir protokol verified olduğuna görə
  sistem kor qalır.
- **Data həcmi artdıqca deqradasiya.**
  - forward_evidence bütün cədvəli yaddaşa yükləyir və kvadratik scan edir;
  - read_queries 5000 sətirlik ORDER BY-siz LIMIT və N+1 sorğular işlədir.
  - Bunlar həftələr sonra OOM, event-loop bloklanması və WebSocket ping itkisi yaradacaq. Bu da öz növbəsində
    yeni gap-lər deməkdir.
- **CI yalançı yaşıl ola bilər.** Secret scanner Solana keypair-lərini (`id.json`, base58) tutmur.
  pip-audit və Trivy CI-da işləmir. ORM↔migration drift yoxlanmır.

---

## 3. Defekt reyestri

Severity: **P0** — məqsədi və ya data bütövlüyünü birbaşa pozur; **P1** — ciddi düzgünlük problemi;
**P2** — orta. "✔" işarəsi bu auditdə kodda əl ilə və ya skriptlə təsdiqləndiyini göstərir.

### 3.1 Data bütövlüyü və stream (P0/P1)

| # | Sev | Yer | Defekt | Ssenari |
| --- | --- | --- | --- | --- |
| S1 ✔ | P0 | `packages/application/.../stream_integrity.py:1452-1476`, `apps/worker/.../early_discovery.py:516` | `GapDetector.detect_resume_boundary` heç yerdə çağırılmır. Restart-dan sonra ilk event-də `reconnect_reason` olmur. | Cursor 1000-də dayanır, worker 1500-də başlayır, 1001–1499 slotları **gap kimi qeyd olunmadan** itir. |
| S2 ✔ | P0 | `packages/providers/.../solana_raw_stream.py:460-481`, `stream_integrity.py:1814` | `getBlocks` `finalized` commitment ilə çağırılır. Hələ finalize olmamış slotlar `produced=False` (skipped) yazılır. Verifier `to_slot ≤ finalized tip` şərtini yoxlamır. | Tip-ə yaxın gap ~13 s ərzində bərpa edilir, son ~32 slot "skipped" sayılır və nəticə **VERIFIED** olur. |
| S3 ✔ | P1 | `solana_raw_stream.py:662, 784` | Reconnect-dən sonra lokal `reconnect_reason` heç vaxt sıfırlanmır, yalnız `_pending_…` sıfırlanır. | Yeni bağlantıdakı hər launch event-i reconnect boundary daşıyır, nəticədə gap storm, full-block backfill və hər yerdə `stream_gap=True`. |
| S4 | P1 | `solana_raw_stream.py:400-408`, `persistence/stream.py:76` | Payload-da `provider_observed_at`, `memeradar_ingested_at` və `commitment` var, equality isə `normalized_payload` üzərindən yoxlanır. | Live və backfill nüsxələri heç vaxt üst-üstə düşmür. Gap CONFLICTED olur və sonsuz retry olunur. |
| S5 ✔ | P1 | `solana_raw_stream.py:452`, `stream_integrity.py:1020` | Adapter limiti 501 slotdur, policy 1000-ə icazə verir, gap bölünmür. Bütün bloklar ardıcıl olaraq bir 10 s-lik `wait_for` daxilində çəkilir. | ~3 dəqiqədən uzun kəsinti daimi FAILED gap qoyur. ~30 slotluq gap da timeout olur. |
| S6 | P1 | `apps/worker/.../main.py:62` | `asyncio.gather` izolyasiyasız və restart-sız işləyir. | Qısa DB kəsintisi bütün prosesi öldürür, S1 isə downtime-ı itirir. |
| S7 | P1 | `packages/application/.../early_worker.py:137-152` | Event yazılır və cursor saxlanılır, sonra processor işləyir. | `runtime.process` xəta verərsə, təkrar çatdırılma DUPLICATE sayılır və candidate heç vaxt score olunmur. |
| S8 | P1 | `apps/worker/.../forward_evidence.py:408-416, 959+`, `early_discovery.py:1145` | Hər poll-da bütün `chain.event` cədvəli yüklənir, kvadratik scan edilir. | Həftələr sonra OOM, event-loop bloklanması, WebSocket ping itkisi və yeni gap-lər. |
| S9 ✔ | P1 | `solana_raw_stream.py:693-782` | `getTransaction` WebSocket `recv` döngüsündə ardıcıl çağırılır (10 s deadline + retry). Yalnız launch-lar çəkilir. | Burst zamanı server buffer-i dolur və disconnect olur. Live trade tape yoxdur. |
| S10 | P2 | `early_worker.py:137`, `stream_integrity.py:1698` | Gap recovery inline işləyir: 4 gap × 3 cəhd × 10 s, ~2 dəqiqə ingest dayanır. | |
| S11 | P2 | `stream_integrity.py:1311-1353` | `record_observation_gap` və `_record_gap` kilidsiz read-merge-write edir. | Gap-lər itə və ya üst-üstə düşə bilər. |
| S12 | P2 | `providers/.../transport.py:384-436` | Hər retry yeni `wait_for` alır, request deadline retry-lar arasında tətbiq olunmur (~3×). | |
| S13 | P2 | `providers/.../jupiter.py:286, 291` | Çatışmayan `priceImpactPct` və `slippageBps` `0` kimi götürülür. | Missing evidence "təhlükəsiz" sayılır. |

### 3.2 Qərar, risk və tədqiqat (lookahead, bias, fail-open)

| # | Sev | Yer | Defekt | Ssenari |
| --- | --- | --- | --- | --- |
| D1 ✔ | P1 | `packages/application/.../early_features.py:440-460`, `early_runtime.py:747-764` | `future_observations_excluded` sayılır, amma `bounded` yalnız event-time ilə filtrlənir. | occurred=T+20s, observed=T+300s, checkpoint T+30s halında müşahidə **istifadə olunur** (skriptlə reproduksiya edildi). Backfill/replay gələcəyi görür. **Qeyd:** runtime checkpoint-i event-time-dır (max `occurred_at`), live-da isə `observed_at` həmişə ondan sonradır. `eligible_at` filtrini sadəcə əlavə etmək bütün live müşahidələri kəsir. Düzəliş checkpoint-in knowledge-time-a (max `observed_at`) keçirilməsini tələb edən dizayn dəyişikliyidir. |
| D2 ✔ | P1 | `early_runtime.py:500-505`, `apps/worker/.../early_discovery.py:907` | `evidence.setdefault("protocol_identity_verified", False)` caller-in `True` dəyərini əvəz etmir. | `stream_gap=True` və ya provider down olduqda FastSafety yenə PASS verir. Invariant pozulur. |
| D3 ✔ | P1 | `launch_risk.py:415-447` | `creator_related` və `fresh_wallet` sahələri yoxdursa nisbət `0/total` olur. | Heç qiymətləndirilməyən creator/fresh-wallet riski PASS verir (skriptlə reproduksiya edildi). |
| D4 | P1 | `flow_analysis.py:1269, 1290` | Quality state-ə quote/sellability daxil deyil. `price_semantics` yoxlanmır. | Sell quote olmadıqda organic flow 100 və FRESH olur. |
| D5 | P1 | `signal_hardening.py:2384-2398` | Bilinməyən `initial_buy_amount` 0 kimi götürülür. | Tam confidence ilə yanlış `DEPLOYER_TRANSFER_DELTA_POSITIVE`. |
| D6 | P2 | `early_runtime.py:557-566`, `early_scoring.py:409`, `decision_engine.py:1009` | Keçici gap və ya STALE risk sübutu score-u 0-a salır, nəticə RISK_REJECTED olur və bu **terminaldır**. | Müvəqqəti RPC problemi qalibi həmişəlik rədd edir (false negative). |
| D7 ✔ | P2 | `early_features.py:809`, `126-133` | `prices[0] == 0` olduqda `DivisionByZero` bütün feature hesabını çökdürür. `price` fallback-i executed və market price-ı qarışdırır. | |
| D8 | P2 | `fast_safety.py:222-231, 397-404` | Generik `quality_state` açarı başqa mənbədən götürülə bilər. Token-security `hard_blocks` birləşdirilmir. | Token-security BLOCK + launch-risk PASS = PASS. |
| D9 | P2 | `signal_hardening.py:257-263` | Default hədlər: 1 buy, 1 alıcı, 1e-9 həcm. | Tək cüzdanla SURGE confirm olur. "Tape-siz momentum yoxdur" invariantı ilə ziddiyyət. |
| D10 | P2 | `correlation.py:1875`, `early_features.py:107` vs `signal_hardening.py:2306` | Faiz/fraksiya ambivalentdir. `amount` bir modulda SOL, digərində token sayılır. | |
| D11 | P2 | `early_runtime.py:916-922` | 1 cüzdan həm WalletQuality, həm SmartMoney komponentini 100 edir (25% çəki). | |

### 3.3 Paper icra, exit, backtest, calibration

| # | Sev | Yer | Defekt | Ssenari |
| --- | --- | --- | --- | --- |
| P1 ✔ | P0 | `apps/worker/.../paper_execution.py:374-401`, `exit_engine.py:1118` | `mark_price()` yalnız sell yolunda çağırılır, high-watermark entry-də qalır. | 3x qalxıb 1.2x-ə düşür, drawdown=0. **TRAILING_STOP və BREAK_EVEN heç vaxt işləmir.** MFE/MAE yazılmır. |
| P2 ✔ | P0 | `apps/worker/.../paper_execution.py:466-492` | Quote xətası və ya impact > limit halında `continue` edilir, time-stop və stop-loss yoxlanmır. | Rug-dan sonra pozisiya **əbədi OPEN** qalır. Zərər realizə olunmur, paper PnL yuxarı qərəzlənir. |
| P3 ✔ | P1 | `exit_engine.py:1083-1108` | Stale və ya missing evidence bütün qaydalardan, o cümlədən qiymət tələb etməyən TIME_STOP-dan əvvəl UNKNOWN qaytarır. | Dump zamanı feed stale olur və stop basdırılır. Burada "fail-closed" = "saxla" deməkdir. Exit üçün yanlış istiqamətdir. |
| P4 | P1 | `backtesting.py:1419-1427, 1642-1690` | `FORWARD_PRICE_MISSING`, `SAFETY_LABEL_UNKNOWN` və s. PnL-dən çıxarılır. | Pool-u yox olan token ~-100% əvəzinə skip olunur. **Survivorship bias**. |
| P5 | P1 | `replay_harness.py:1588-1676, 2078` | Horizon `(signal, end]` aralığında hər hansı record olduqda FRESH sayılır. `end ≤ as_of` yoxlanmır. | 24 saatlıq label faktiki olaraq 2 saatlıq qiymətlə hesablanır. |
| P6 | P1 | `calibration.py:197-207, 1366`, `scripts/calibrate_score.py:94` | Split-lər arasında embargo yoxdur (label 24 saat, pəncərə 1 gün). | TRAIN label-ları VALIDATION qiymətlərindən qurulur. **Leakage**. |
| P7 | P1 | `backtesting.py:1355-1377` | Rug/liquidity label-i horizon sonunda exit-i məcbur edir, hətta TP və ya stop daha əvvəl vurulubsa belə. | Lookahead. Exit vaxtı və qiyməti yanlışdır. |
| P8 | P1 | `backtesting.py:1393-1402` | Stop vaxtı `drawdown_fraction`-dan, səviyyəsi isə `stop_loss_fraction`-dan götürülür. Ikisi yalnız default-da (0.5) üst-üstə düşür. | `stop_loss=0.2` olduqda -20% exit -50%-in vaxtında baş verir. |
| P9 | P1 | `backtesting.py:1474-1601` | Stop və TP trigger qiymətində fill olur (gap-through yoxdur). Reference price executed price kimi istifadə olunur, impact=0. | Memecoin-lərdə drawdown ciddi şəkildə az göstərilir. |
| P10 | P1 | `backtesting.py:1076-1150` | Konkurensiya, kapital və ya token-dedup limiti yoxdur. | Bir tokenin 10 checkpoint-i 10 korrelyasiyalı trade sayılır. 20 trade-lik promotion gate asanlıqla keçilir. |
| P11 | P1 | `caller_outcomes.py:780-797` | Executable MAE yalnız satıla bilən nöqtələri sayır. | Rug-dan sonrakı çöküş MAE-yə düşmür. Caller statistikası yuxarı qərəzlənir. |
| P12 | P2 | `calibration.py:1388-1470` | Seçim TRAIN expectancy ilə aparılır. Minimum nümunə, CI və multiple-testing korreksiyası yoxdur. | 1 trade-lik +400% namizəd 200 trade-lik namizədi üstələyir. |
| P13 | P2 | `operations.py:333-337` | `average_exit` yalnız son partial fill-dən götürülür, VWAP deyil. | |
| P14 | P2 | `paper_execution.py:1781-1799` | Keçmiş `as_of` üçün reconcile-də yanlış `CASH_BALANCE_MISMATCH`. Baseline qiymətin yaş limiti yoxdur. | |
| P15 | P2 | `paper_execution.py:1580` | EXIT_SIGNALLED pozisiyanın satışı `mark_price` daxilində ValueError atır (latent). | |

### 3.4 API, persistence, infra, CI və təhlükəsizlik

| # | Sev | Yer | Defekt |
| --- | --- | --- | --- |
| I1 ✔ | P1 | `requirements.lock`, `pyproject.toml` | `aiosqlite` yoxdur. Təmiz bootstrap-da test suite və CI qırılır (§1). |
| I2 ✔ | P1 | `packages/persistence/.../read_queries.py:697-705, 1187` | `LIMIT 5000` ORDER BY olmadan, hər sətir üçün 2× `session.get`, pagination yaddaşda aparılır. 5000-dən çox candidate olduqda yeni candidate-lər **itə bilər**. ~10k round-trip. |
| I3 | P1 | `read_queries.py:1517-1540` | `list_positions`: ORDER BY yoxdur, sətir başına 4 sorğu. 5+5 connection pool tükənir. |
| I4 ✔ | P1 | `application/.../manual_submission.py:57-88`, `apps/api/.../manual.py:79` | `POST /v1/manual/mints` yalnız in-memory `set`-də saxlanılır, DB və ya outbox-a yazılmır. Operator 200 alır, worker isə mint-i heç vaxt görmür. |
| I5 | P1 | `scripts/secret_scan.py:20-27` | Solana keypair (64 baytlıq JSON array, base58), Helius UUID və `sk-ant-` tutulmur. Commit olunmuş `id.json` CI-dan keçir. |
| I6 | P1 | `scripts/security_review.py:94-102, 583-611`, CI | Xarici skanerlər NOT_RUN olduqda belə nəticə PASS olur. pip-audit və Trivy CI-da yoxdur. |
| I7 | P1 | `scripts/check_migrations.py`, CI | ORM↔migration drift (`compare_metadata`) və downgrade testi yoxdur. |
| I8 | P2 | `infra/alembic/versions/0007_multichain_identity.py:28-32` | Multichain mint olduqda downgrade qırılır. |
| I9 | P2 | `apps/api/.../read/__init__.py:343-353`, `operations.py:185` | Token konfiqurasiya olunmayıbsa read route-ları (`/v1/audit/events`, `/v1/config/versions`) açıqdır. |
| I10 | P2 | `read_queries.py:810-1040` | `/v1/readiness` `observations` cədvəlində 8–10 COUNT işlədir: JSON (JSONB deyil), indeks yoxdur, hər 30 s poll olunur. |
| I11 | P2 | `infra/compose/*` | Prod-da da Redis `requirepass`-sızdır. Worker və web üçün healthcheck yoxdur. Migrasiya servisi yoxdur. `NEXT_PUBLIC_*` runtime-da verilir, halbuki build-time-da inline olunur. Image-lər digest ilə pin edilməyib, `apt-get upgrade` istifadə olunur. |
| I12 | P2 | `.github/workflows/ci.yml` | Action-lar SHA ilə pin edilməyib. |
| I13 | P2 | `apps/worker/.../operations_jobs.py:45-60` | Outbox-da yalnız `CandidateStateChanged` göndərilir. RiskEscalation, PaperExit, ExitSignal, KillSwitch "handled" kimi ack olunur, amma göndərilmir. |
| I14 | P2 | `operations_jobs.py:64-160` | Health loop-da exception handling yoxdur. Shutdown zamanı `aclose()` və `dispose()` atlanır. |
| I15 | P2 | `apps/mcp/.../server.py:272-285` | API xətaları `isError: false` ilə qaytarılır. |

---

## 4. Yarımçıq və ya qoşulmamış funksionallıq

| Sahə | Vəziyyət | Məqsədə təsiri |
| --- | --- | --- |
| **ENTRY_READY** | `OrganicFlowAcceleration` `None`-a hard-code edilib (`early_runtime.py:924`). 0.25 çəki həmişə yoxdur, -10 INCOMPLETE cəzası tətbiq olunur, score tavanı ~65-dir, giriş həddi isə 85-dir. | **Erkən giriş siqnalı istehsalda əlçatmazdır.** |
| Live trade tape | Yalnız launch-lar çəkilir. Backfill bütün instruction-ları decode edir, live isə yox. Live və replay asimmetrikdir. | Flow, momentum və sniper analizi qidalanmır. |
| Protokol identikliyi | Yalnız Pump.fun VERIFIED. PumpSwap, Raydium v4/CPMM/CLMM, Meteora isə TODO_VERIFY. | Miqrasiyadan sonrakı faza (ən böyük upside) autoritativ deyil. |
| Signal hardening | `SignalHardeningAnalyzer` yalnız replay-də işləyir, scoring və risk-ə daxil deyil. `window_start` nəzərə alınmır. | Diaqnostikadır, qərara təsir etmir. |
| Launch-risk supply sahələri | `mint_authority`, `freeze_authority`, Token-2022 extension-ları və top-holder disposition-a təsir etmir. | Rug detektoru yalnız qismən işləyir. |
| Provider adapterləri | Helius stream/webhook, Birdeye fallback, GoPlus, Chainlink, evm_sellability, pump_fun_protocol_drift instansiya edilmir. RugCheck `assess()` çağırılmır. | Risk sübutlarının əhatəsi dardır. |
| Paper risk idarəsi | `PaperSizingPolicy.size()` istifadə olunmur (sabit `entry_size_sol`). Avtomatik drawdown və ya daily-loss kill-switch yoxdur. Paper worker manual kill-switch-ə baxmır. EXIT_SIGNALLED heç vaxt set edilmir. Liquidity decay, smart-money və creator distribution exit qaydalarına input verilmir. | Exit tərəfi "asimmetrik upside-ı qorumaq" məqsədini hələ yerinə yetirmir. |
| Settings hot-reload | Control router `settings_provider` və `apply_hot_settings` qəbul edir, amma `main.py` onları ötürmür. | UI-dan saxlanan settings tətbiq olunmur. |
| Manual mint intake | Yalnız in-memory ack var (I4). | |
| Legacy evidence loophole | `evidence_policy.py:27-43`: 2026-09-15-dən əvvəlki, `collection_mode`-suz müşahidələr production evidence sayılır. | Kohort çirklənməsi riski. |

---

## 5. Performans dar boğazları

1. **Live ingest.** `getTransaction` ardıcıl çağırılır və `recv` döngüsünü bloklayır (S9). Gap recovery də inline
   işləyir (S10). Bunlar bounded `asyncio` worker pool-a və ayrı recovery task-a çıxarılmalıdır.
2. **Backfill.** Hər slot ardıcıl `getBlock` ilə alınır (S5), `max_concurrency` nəzərə alınmır. Bounded concurrency
   tətbiq etmək, gap-i 500 slotluq chunk-lara bölmək və `wait_for` timeout-unu chunk başına tətbiq etmək lazımdır.
3. **Forward evidence.** Tam cədvəl scan-ı və O(n²) yanaşma var (S8). Inkremental cursor və `(token_id, slot)`
   indeksi lazımdır.
4. **Read API.** N+1 sorğular, ORDER BY-siz limit, JSON üzərində COUNT (I2, I3, I10). Lazım olanlar:
   - `selectinload`/join;
   - keyset pagination;
   - JSONB + GIN indeksi və ya materialized readiness counter.
5. **`list_gaps`.** Hər event-də bütün VERIFIED tarixçə oxunur. Sorğu yalnız aktiv statuslarla məhdudlaşdırılmalıdır.

---

## 6. Prioritetləşdirilmiş remediation planı

Ardıcıllıq vacibdir: əvvəlcə **ölçmə aləti**, sonra **data bütövlüyü**, sonra **qərar** düzəldilir.

**Faza A — Reproducibility (0.5 gün)**
- `aiosqlite` paketini `requirements.lock`/dev qrupuna əlavə et. CI-ın təmiz bootstrap-dan yaşıl olduğunu sübut et.
- Secret scanner-ə Solana keypair və `sk-ant-` pattern-ləri əlavə et.
- CI-a `alembic check` və ya `compare_metadata` əlavə et.

**Faza B — Stream bütövlüyü (P0, 2–3 gün)**
- S1: startup-da `detect_resume_boundary` çağır, persistent cursor ilə ilk event arasında `RESUME_BOUNDARY` gap aç.
- S2: backfill-də `to_slot ≤ getSlot(finalized)` şərtini tələb et, əks halda `DEFERRED` qaytar.
- S3: ilk uğurlu event-dən sonra lokal `reconnect_reason = None`.
- S4: equality-ni transport metadata-sı çıxarılmış canonical payload üzərindən apar.
- S5: gap-i ≤500 slotluq chunk-lara böl, bounded concurrency tətbiq et.
- S6/S7: hər task üçün supervisor (restart + backoff). Processor uğurlu olandan sonra "processed" marker qoy (outbox/inbox pattern).
- Testlər: sintetik restart gap-i, tip-ə yaxın gap, reconnect-dən sonrakı ardıcıl event-lər.

**Faza C — Tədqiqat etibarlılığı (P1, 3–4 gün)**
- D1: `bounded` filtrinə `eligible_at` (observed/ingested ≤ checkpoint) əlavə et.
- P4: missing forward price və ya pool yoxdursa `-100%` (və ya konfiqurasiya edilə bilən worst-case) kimi saxla, skip etmə.
- P5: horizon coverage-ı yoxla (`last_obs ≥ end - tolerance` və `end ≤ as_of`), əks halda INCOMPLETE qaytar.
- P6: split-lər arasında `embargo ≥ max horizon` tətbiq et (purged walk-forward).
- P7/P8/P9: label və stop parametrlərini birləşdir. Gap-through fill-i növbəti müşahidə qiymətində apar. Impact modeli əlavə et.
- P10/P12: tokenə görə dedup. Minimum N, bootstrap CI, Bonferroni/BH korreksiyası və ya ayrıca hold-out tətbiq et.

**Faza D — Fail-closed düzəlişləri (P1, 1–2 gün)**
- D2: `setdefault` əvəzinə məcburi override istifadə et (`evidence["protocol_identity_verified"] = False`).
- D3/D5/S13: missing sahələr `UNKNOWN`/None olmalıdır, `0` yox. Bunun üçün regression testləri yaz.
- D4 və `early_decision.py:470-482` (`_quote_valid`): `price_semantics == EXECUTION_QUOTE` yoxlanışı əlavə et.
- D6: STALE/UNKNOWN risk sübutu terminal REJECT deyil, `WATCH_PENDING_EVIDENCE` olmalıdır.

**Faza E — Paper exit (P0, 2 gün)**
- P1: exit monitor-da hər etibarlı quote ilə `mark_price` çağır. MFE/MAE yaz. Trailing qayda üçün "consumed" vəziyyəti saxla.
- P2/P3: quote yoxdursa da TIME_STOP qiymətləndirilsin. N dövr quote olmadıqda `UNEXECUTABLE`-ı worst-case qiymətlə qeyd et və ayrıca hesabata çıxar.
- Avtomatik drawdown/daily-loss kill-switch əlavə et. Paper worker `execution_kill_switch`-ə baxsın.

**Faza F — Alpha üçün tutum (1–2 həftə, ölçülmüş ehtiyacdan sonra)**
- Live trade tape (logsSubscribe + bounded worker pool) qur və `OrganicFlowAcceleration`-u qoş.
- PumpSwap/Raydium identikliyini müstəqil verifikasiya et.
- Ödənişli RPC və ya Yellowstone gRPC istifadə et. Hədəf metrikalar: create→observed p95 latency və gap rate.
- Bu fazadan sonra 4–8 həftəlik **dondurulmuş** forward kohort topla. Matched baseline ilə müqayisə et. Hər
  multiplikator səviyyəsi (2x/10x/20x+) üçün Wilson CI ilə hit-rate hesabla.

**Faza G — Əməliyyat və təhlükəsizlik (paralel)**
- I2/I3/I10 query optimallaşdırması və indekslər.
- I11: Redis auth, healthcheck-lər, migrasiya init servisi, digest pin.
- I13: bütün outbox növlərini göndər.
- pip-audit və Trivy-ni CI-a əlavə et.

---

## 7. Monitorinq tövsiyələri (SLO-lar)

| Metrik | Mənbə | Alert həddi (ilkin hipotez) |
| --- | --- | --- |
| `stream.gap.open_slots` | stream_integrity | > 0, 5 dəqiqədən çox |
| `stream.resume_gap_detected_total` | S1 düzəlişi | hər restart-da > 0 olmalıdır (0 olarsa detektor işləmir) |
| `ingest.create_to_observed_ms` p95 | solana_raw_stream | > 2000 ms |
| `rpc.getTransaction.unavailable_rate` | solana_raw_stream | > 2% |
| `paper.positions.unquotable_age_s` max | paper worker | > TIME_STOP |
| `paper.trailing_armed_total` | exit engine | 7 gün ərzində 0 olarsa xəbərdarlıq (P1 regressiyası) |
| `decision.entry_ready_total` | decision engine | 0 olarsa ENTRY_READY əlçatmazlığına işarədir |
| `outbox.unsupported_kind_acked_total` | operations_jobs | > 0 |

---

## 8. Doğrulama qeydləri

- Lokal qovluqda yoxlanılmalı olanlar: `artifacts/verification/` sübutları, `.venv`-də `aiosqlite`-ın necə quraşdırıldığı,
  PostgreSQL inteqrasiya suite-i (`make integration-test`) və Playwright.
- Agentlərin "medium" etibarlılıqla verdiyi tapıntılar (S4, S11, D8–D10, I10) düzəlişdən əvvəl reproduksiya testi
  ilə təsdiqlənməlidir.
- Bu audit `ANALYSIS_ONLY` və `PAPER_TRADING` rejimlərini dəyişmir. Heç bir secret oxunmayıb və ya ötürülməyib.

---

## 9. Remediation statusu (eyni gün, `claude/exciting-brahmagupta-0k7pds`)

Hər düzəliş regression testi ilə gəlir. Testlərin düzəlişdən əvvəl FAIL, sonra PASS etdiyi yoxlanıb.
Sonda Ruff, mypy (187 fayl) və tam non-integration suite (1664 passed) keçir.

| Tapıntı | Commit | Nə dəyişdi |
| --- | --- | --- |
| I1 | `18a44c4` | `aiosqlite==0.22.1` lock və dev qrupuna əlavə olundu. Secret scan Solana keypair array, `sk-ant-` və UUID `api-key` query-ni tutur. |
| D2 | `107a888` | Gap, provider outage və non-direct detection zamanı `protocol_identity_verified` məcburi `False` olur. |
| S3 | `1e2fc70` | Reconnect boundary yalnız yeni bağlantıdakı ilk event-də qalır. |
| S2 | `ed9f4fc` | Backfill finalized tip-i (`getSlot finalized`) oxuyur. Tip-dən o tərəfə keçən aralıq `BACKFILL_UNAVAILABLE` olur və gap açıq qalır. |
| P1 (paper) | `9f16c32` | Exit monitor açıq pozisiyanı executable exit-quote qiyməti ilə monoton mark edir (`save_position_mark`). Trailing stop və break-even işləyir, MFE/MAE yazılır. SQL yolu sqlite ilə yoxlandı, PostgreSQL integration testinə assert əlavə olundu. |
| D3 | `5e2fd32` | Creator/fresh-wallet atributu olmayan aktorlar UNKNOWN sayılır. Qismən qiymətləndirmə yalnız aşağı sərhəd blok həddinə çatdıqda nəticə verir. |
| S13 | `5c48fc7` | Jupiter quote-u `priceImpactPct` olmadan rədd edilir. `slippageBps` olmadıqda tələb olunan tolerans götürülür. |
| D7 | `3e1c9d5` | Sıfır ilk qiymət `return=None` verir, feature hesabı çökmür. |
| I2/I3 | `c8e90da` | Candidate və position read-ləri newest-first sıralanır (N+1 hələ qalır). |
| S1 | `114be06` | Yeni mənbənin ilk event-i `PROCESS_START` boundary daşıyır. Coordinator restart downtime-ını durable cursor-a nisbətən gap kimi qeyd edir. |

**Açıq qalanlar (növbəti prioritet):**
- P2/P3 — zombi pozisiyalar və quote olmadıqda TIME_STOP. Bunun üçün unexecutable pozisiyanın hansı qiymətlə bağlanacağına dair policy qərarı lazımdır.
- D1 — checkpoint semantikasının knowledge-time-a keçirilməsi.
- §3.2/§3.3-dəki backtest və calibration bias-ları (P4–P12).
- S4–S12 — stream recovery etibarlılığı. Xüsusilə gap-in ≤500 slotluq chunk-lara bölünməsi (S5) vacibdir: S1-dən sonra uzun downtime gap-ləri artıq görünür, amma 501 slotdan böyük olduqda bərpa oluna bilmir.
- I4–I11 — API, CI və infra.
- `ENTRY_READY` əlçatmazlığı (`OrganicFlowAcceleration` qoşulmayıb).
