# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | Türkçe | [Polski](../pl/README.md) | [Українська](../uk/README.md)

Bu belge bir çeviridir; esas alınan kaynak [İngilizce sürümdür](../../../README.md).

kolabse tarafından bakımı yapılan, yeniden kullanılabilir ajan becerileri.

[Apache Lisansı 2.0](../../../LICENSE) kapsamında lisanslanmıştır. Telif hakkı 2026 kolabse.

## İçindekiler

- [Becerileri kurma](#becerileri-kurma)
  - [Git marketlerinden kurma](#git-marketlerinden-kurma)
- [Kurulu becerileri güncelleme](#kurulu-becerileri-güncelleme)
  - [Depoyu klonlamadan çalıştırma](#depoyu-klonlamadan-çalıştırma)
  - [Genel kurulumları inceleme](#genel-kurulumları-inceleme)
- [Yerel geliştirme için Codex eklentisi kurma veya güncelleme](#yerel-geliştirme-için-codex-eklentisi-kurma-veya-güncelleme)
- [Mevcut beceriler](#mevcut-beceriler)
  - [Geliştirme ve kod kalitesi](#geliştirme-ve-kod-kalitesi)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-deneysel)
    - [`review-code-changes`](#review-code-changes-deneysel)
    - [`diagnose-software-defects`](#diagnose-software-defects-deneysel)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-deneysel)
  - [Depolar ve değişiklik teslimi](#depolar-ve-değişiklik-teslimi)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-deneysel)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-deneysel)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-deneysel)
  - [Proje bilgisi ve süreklilik](#proje-bilgisi-ve-süreklilik)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-deneysel)
    - [`sync-project-context`](#sync-project-context)
  - [Koordinasyon ve iletişim](#koordinasyon-ve-iletişim)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-deneysel)
    - [`synchronize-team-skills`](#synchronize-team-skills-deneysel)
    - [`report-skill-feedback`](#report-skill-feedback-deneysel)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Altyapı ve operasyonlar](#altyapı-ve-operasyonlar)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Beceri koleksiyonunun gelişimi](#beceri-koleksiyonunun-gelişimi)
    - [`discover-skill-candidates`](#discover-skill-candidates-deneysel)
    - [`release-skill-collection`](#release-skill-collection)
- [Desteklenen bileşimler](#desteklenen-bileşimler)
- [Beceri ekleme](#beceri-ekleme)
- [Bir sürümü doğrulama](#bir-sürümü-doğrulama)

## Becerileri kurma

Ajanlar arası [`skills`](https://skills.sh) CLI ile mevcut kullanıcı için bir
veya daha fazla beceriyi genel olarak kurun:

```shell
npx skills@latest add kolabse/skills --global
```

CLI, `skills/` altındaki klasörleri keşfeder, kurulacak becerileri seçmenize
olanak tanır ve bunları seçilen kodlama ajanlarına kopyalar. Bu harici bir
kurucudur; bu depo kendi npm paketini yayımlamaz veya çalıştırmaz.

Codex kullanıcıları alternatif olarak `$skill-installer` aracından bu depodan
bir beceri kurmasını isteyebilir; örneğin şu konumdan:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Etkileşimsiz kurulum için açıkça bir tüketici seçin:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

Ajanınıza şunu söyleyin: "Seçilen becerileri genel olarak kur ve mevcut
kuralları değiştirmeden bu projenin yalnızca eksik yapılandırmasını başlat."
Ardından genel beceri yolunu kullanın:

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Eksik kurallar varsayılan olarak `feature/`, `bugfix/`, `release/`, `hotfix/`
ve `feat`, `fix`, `refactor`, `docs`, `test`, `chore` commit türlerini kullanır.
Projenin açıkça belirttiği önekler, dal rolleri ve commit biçimleri esas olmaya
devam eder. Kalıcı dallar veya Git kancaları oluşturulmaz. Yönetilen genel
güncellemeler aynı başlangıç işlemini açıkça seçilen etkin projeye uygular;
onaylanmamış güncellemeler yalnızca bunu planlar.

Gözlemlenebilir varsayılanları yeterliyse proje yaşam döngüsü sözleşmesini hemen
başlatın (ajanınıza uygun yolu kullanın):

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Market/eklenti kurulumları geneldir ve etkin proje kökleri yoktur; bu nedenle
beceri aynı başlangıç işlemini projedeki ilk kullanımda yapar.

Desteklenen genel yollar Codex için `~/.agents/skills/`, Claude Code için
`~/.claude/skills/` dizinleridir. Projelerde bu payload klasörlerinin dışında
yalnızca yapılandırma, yönetilen kurallar ve kasıtlı proje ayarları tutulur.

Depo ayrıca ChatGPT/Codex ve Claude Code için yalnızca beceriler içeren
`kolabse-skills` eklentisi olarak paketlenir. `skills/` altındaki her klasör
dahildir. Ajanlar arası `npx skills` kurulumu her iki eklenti biçiminden
bağımsız olarak kullanılabilir.

### Git marketlerinden kurma

Codex kullanıcıları depo marketini kaydedip tüm koleksiyonu şu komutlarla kurabilir:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Git anlık görüntüsünü yenileyip güncel eklenti sürümünü yeniden kurun:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Claude Code kullanıcıları aynı depoyu kaydedip eklentiyi şu komutlarla kurabilir:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

`claude plugin marketplace update kolabse` ile açıkça yenileyin veya Claude
Code'da market otomatik güncellemesini etkinleştirin. Güncel beceri kümesinin
keşfedilmesi için kurulum veya güncellemeden sonra yeni bir ajan oturumu başlatın.

Market katalogları [`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
ve [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json)
dosyalarıdır. Eklenti içerikleri [`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json)
ve [`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json) ile
tanımlanır. Her iki katalog da esas `kolabse/skills` deposunu `main` dalından
alır; sürüm numaralandırmasında eklenti manifestleri esas olmaya devam eder.

Herkese açık listeleme materyallerinin bakımı kaynakla birlikte yapılır:
[destek](SUPPORT.md), [gizlilik politikası](PRIVACY.md), [kullanım koşulları](TERMS.md)
ve yeniden üretilebilir [market başvuru paketi](../../../docs/marketplace-submissions/).
Resmî bir dizinde yayımlama, bakım sorumlusunun incelemeye tabi eylemi olmaya
devam eder; Git marketlerinden kurulum dizin onayı gerektirmez.

Claude Code, test sırasında çıkarılmış bir sürümü veya güvenilen çalışma
kopyasını `claude --plugin-dir <collection-root>` ile doğrudan yükleyebilir.
Olağan kişisel veya proje kullanımı için Git marketini ya da yukarıdaki açık
`npx skills ... --agent claude-code` komutunu tercih edin. Claude Code,
`AGENTS.md` değil `CLAUDE.md` okur; projede zaten paylaşılan `AGENTS.md` kuralları
varsa `@AGENTS.md` içeren en küçük `CLAUDE.md`, tek bir esas kural belgesini korur.

## Kurulu becerileri güncelleme

`skills` CLI, genel kaynakları ve içerik özetlerini `~/.agents/.skill-lock.json`
içine kaydeder. Genel kurulumları kayıtlı kaynaklarından güncelleyin:

```shell
npx skills@1.5.22 update -g -y
```

Tek bir beceriyi veya genel kurulumları güncelleyin:

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

Eski proje kapsamlı kopyalar plan incelendikten sonra merkezileştirilmelidir.
Geçiş önce genel kopyayı kurup doğrular, eski payload’ı yedekler ve proje
yapılandırmasıyla ilgisiz becerileri korur:

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

Sürüm belirtilmemiş bir `kolabse/skills` kilidi deponun varsayılan dalını izler;
bir koleksiyon sürümünü sabitlemez. Güncelleme yerine yazabileceği için genel
payload kopyalarını düzenlemeyin. Proje ve kullanıcı yapılandırması kurulu
beceri klasörleri dışında kalır.

Klonlanmış bir çalışma kopyasından veya sürüm arşivinden, desteklenen proje
yapılandırmasını tek bir açık işlemde güncelleyin ve taşıyın:

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

Harici kurucuyu çağırmadan veya yapılandırmayı değiştirmeden tam seçimi önizleyin:

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

Plan; kaynak kimliğini, mevcut ve hedef sürümleri, kökeni, geçiş adaylarını ve
`update`, `unchanged`, `adopt-and-update` veya `blocked` eylemlerini bildirir.
Şeması `schemas/manager-plan.schema.json` dosyasıdır. `update` komutuna `--json`
ekleyin; güncelleme ve geçiş sonuçları `schemas/manager-result.schema.json`
şemasına uyar.

Ad verilmediğinde yönetici yalnızca genel kilitteki kolabse becerilerini çözümler;
diğer genel beceriler dahil edilmez. Eski proje güncellemesi yalnızca bildirim
ve geçiş için geçici yol olarak kalır. `execute-verified-development-lifecycle`
genel olarak güncellendiğinde yönetici, proje olguları yeterliyse eksik
yapılandırmasını da başlatır ve `created`, `configured` veya `blocked`
yapılandırma sonucu döndürür.

`--include-user-config` yalnızca Telegram kullanıcı yapılandırmasının da
taşınması gerekiyorsa eklenmelidir. `status` ve `doctor` salt okunurdur.
`migrate` yalnızca mevcut yapılandırma dosyalarını değiştirir; kullanılmayan
becerileri yapılandırmaz. Kurulu her beceri `collection-metadata.json` taşır;
bu nedenle harici kilit biçiminde sürüm alanı olmasa bile `status` koleksiyon
sürümünü bildirir. Ayrıca `provenance_status` bildirir: `verified` hem
koleksiyon meta verilerini hem esas GitHub kaynağını veya içeriği doğrulanmış
yerel kilit kaynağını gerektirir; `legacy-unverified` meta veriden önceki
kurulumu belirtir; `mismatch` asla güncellenmez. Yerel kimlik dizin adından
değil eklenti manifestinden, katalogdan ve beceri içeriklerinden geldiği için
çalışma kopyası yeniden adlandırılabilir.

Meta verisiz, v1.2 öncesi bir kurulumu ancak bildirilen kaynağını inceledikten
sonra benimseyin:

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

Benimseme bayrağı rastgele dosyaları güvenilir kılmaz: kaynak zaten
`kolabse/skills` biçimine normalleşmeli veya yerel çalışma kopyası doğrulamasını
geçmelidir; normal güncelleme sonrası tanı da kurulu meta verileri doğrulamalıdır.
Harici CLI, `sourceType: local` geliştirme kilitlerini yerinde güncellemez.
Yönetici CLI'nin bu etkisiz işlemini başarısızlık sayar; bu becerileri özgün
`--skill` ve `--agent` seçimleriyle yerel kaynaklarından yeniden ekleyin.

### Depoyu klonlamadan çalıştırma

`scripts/bootstrap_update.py` dosyasını güvenilir bir sürümden veya bu depodan
indirin; ardından en son kararlı sürümü çözümlemesini, sürüm ZIP'ini
`SHA256SUMS` ve GitHub derleme kökeniyle doğrulamasını ve yöneticiyi yalıtılmış
bir geçici çıkarma dizininden çalıştırmasını sağlayın:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Bir sürümü sabitlemek için `--release v1.15.0` kullanın. Başlangıç yardımcısı
tasdik doğrulaması için `gh` gerektirir ve tamamlandığında geçici dizinini
kaldırır. Çevrimdışı önbellek için hem `--offline-archive` hem
`--offline-checksums` sağlayın. `gh` GitHub'a erişebiliyorsa köken doğrulaması
zorunlu kalır. `--allow-unattested-offline` açık bir kısıtlı güvence modudur:
yalnızca önbellekteki sağlama toplamını doğrular ve sadece bağımsız olarak
güvenilen bir kanaldan taşınmış çıktılar için kullanılmalıdır. Eski bir sürümü
seçip mevcut geri alma prosedürünü kullanarak geri alın; yapılandırma geçişleri
yalnızca ileri yöndedir.

### Genel kurulumları inceleme

Desteklenen genel durum bilinçli olarak paylaşılan `~/.agents/.skill-lock.json`
v3 kilidiyle sınırlıdır. Kurulu içerikler Codex için `~/.agents/skills`, Claude
Code için `~/.claude/skills` içinde bulunur. Yönetici diğer kullanıcı dizinlerini
taramaz. Codex varsayılan olarak kalır; Claude içerik düzeni için
`--agent claude-code` geçirin:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Bir test düzenini veya açıkça taşınmış uyumlu düzeni salt okunur incelemek için
`--global-root` kullanın. Harici CLI bunları hedefleyemediği için taşınmış
kökler güncellenemez. Bilinmeyen kilit biçimleri değişiklik yapılmadan bildirilir.

Beceri dosyalarını geri almak için önce proje/kullanıcı yapılandırmasını
yedekleyin, ardından özgün kurulumdaki aynı beceriler ve ajan hedefleriyle
gerekli sürüm etiketini yeniden kurun; örneğin:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

Bir sürüm açıkça eski sürüme geçişi belgelemedikçe yapılandırma geçişleri yalnızca
ileri yöndedir. Eski beceri dosyalarını geri yüklemek yapılandırmayı eski
sürüme düşürmez; eski sürüm yeni biçimi okuyamıyorsa eşleşen yapılandırma
yedeğini geri yükleyin.

## Yerel geliştirme için Codex eklentisi kurma veya güncelleme

Yerel eklenti geliştirmesi için varsayılan kişisel market kaydını
oluşturun/güncelleyin, eklentiyi yerel eklenti dizinine kopyalayın, Codex
önbellek yenileme eki ekleyin ve etkinleştirin:

```shell
python scripts/install_personal_plugin.py --activate
```

Kurucu, diğer kişisel market kayıtlarını korur ve depo manifestini düzenlemez.
Bu, normal Git marketi kurulumu değil, alternatif bir geliştirme yoludur.
Çalışma kopyasını güncelledikten sonra yeniden çalıştırın, ardından güncel
becerilerin yüklenmesi için yeni bir Codex görevi başlatın. Kurulu sürümü,
eklenti yolunu, market yolunu ve market adını kaydetmek için `--json` kullanın.

## Mevcut beceriler

Kararlı beceriler ve deneysel eklemeler `skill-catalog.json` içinde belirtilir.
Projeye yönelik yapılandırma yolları, güvenlik sınırları ve belgelenmiş komut
arayüzleri [CONTRIBUTING.md](CONTRIBUTING.md) içindeki uyumluluk politikasına uyar.

Artık her katalog kaydı yapılandırma kapsamını, salt okunur JSON durum komutunu,
yetenekleri, ön koşulları ve isteğe bağlı entegrasyonları bildirir. Durum tutan
beceriler ayrıca idempotent bir yapılandırma komutu bildirir; sürümlenmiş
JSON/YAML yapılandırmaları becerinin yanında bir JSON Schema ve geçiş komutu yayımlar.

Katalog, aşağıdaki öncelik sırasıyla, kullanıcıya yönelik birincil amacına göre
gruplanmıştır. Her becerinin tam olarak bir birincil kategorisi vardır.
Bağımsız etiketler yaşam döngüsü aşamasını, kapsamını, davranışını ve
entegrasyonlarını tanımlar; olgunluk durumu bunlardan bağımsızdır. Esas alınan,
makine tarafından okunabilir atamalar ve kontrollü terimler
[`skill-catalog.json`](../../../skill-catalog.json) içinde bulunur ve
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json)
ile doğrulanır.

Kontrollü etiket eksenleri şunlardır:

- yaşam döngüsü aşaması: `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` ve `handoff`;
- kapsam: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` ve `skill-collection`;
- davranış: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` ve `notification`;
- entegrasyon: `git`, `github`, `telegram`, `google-drive` ve `yandex-cloud`.

### Geliştirme ve kod kalitesi

#### `develop-with-test-first-evidence` (deneysel)

Davranışı kanıta dayalı kırmızı-yeşil-yeniden düzenleme döngüleriyle uygulayın.

**Ne yapar:**

- uygulamadan önce hedeflenen davranışsal nedenle başarısız olan odaklı bir
  testi kaydeder;
- odaklı ve daha geniş kapsamlı başarılı sonuçları nihai değişiklik durumuna bağlar;
- kalıcı kanıtları paketlenmiş şeması ve yardımcısıyla doğrular.

**Ne yapmaz:**

- ilgisiz davranışı bozarak başarısız bir sonuç üretmek;
- sonradan yazılan testleri test öncelikli geliştirme olarak adlandırmak;
- önceden var olan, ortam kaynaklı veya son durumdaki başarısızlıkları gizlemek.

**Nasıl çağrılır:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (deneysel)

Tanımlanmış bir değişikliği, eyleme geçirilebilir doğruluk, güvenlik,
güvenilirlik ve uyumluluk kusurları açısından inceleyin.

**Ne yapar:**

- kesin bir temel durumu ve değişmiş durumu belirler;
- etkisi, tetikleyicisi, önceliği ve dar konumlarıyla kanıta dayalı bulgular bildirir;
- belirsizliği ve anlamlı test boşluklarını açıkça belirtir.

**Ne yapmaz:**

- biçem tercihlerini veya dayanaksız varsayımları kusur olarak bildirmek;
- ayrıca yetki verilmeden bulguları uygulamak, yorum yayımlamak veya incelemeyi
  onaylamak;
- kapsamı belirlenmiş incelemenin yerine genel bir kod açıklaması sunmak.

**Nasıl çağrılır:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (deneysel)

Desteklenmiş bir nedensel açıklama veya sıralanmış hipotezler üretmek için
başarısızlıkları ve regresyonları araştırın.

**Ne yapar:**

- belirtiyi sınırlar ve mümkün olduğunda güvenli biçimde yeniden üretir;
- rakip hipotezleri ilgili kanıtlarla sınar;
- kök nedeni, katkıda bulunan koşulları, etki alanını, güven düzeyini ve
  düzeltme doğrulama planını bildirir.

**Ne yapmaz:**

- korelasyondan nedensellik çıkarmak;
- üretim ortamını değiştirmek veya başarısızlık kanıtlarını atmak;
- yalnızca tanı istendiğinde varsayıma dayalı düzeltme uygulamak.

**Nasıl çağrılır:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (deneysel)

Yetkilendirilmiş merge, rebase veya cherry-pick çakışmalarını ilgisiz çalışmayı
koruyarak anlamsal olarak çözün.

**Ne yapar:**

- etkin işlemi, temeli, her iki tarafı ve birleştirilmemiş her yolu inceler;
- yalnızca amaçlanan birleşik davranışın anlaşıldığı çakışmaları uzlaştırır;
- çözülen yolları doğrular ve kalan Git işlem adımını açıkça belirtir.

**Ne yapmaz:**

- olağan depo ayrışmasını dosya çakışması görevi olarak değerlendirmek;
- otomatik stash, reset, abort, continue, force-push yapmak veya ilgisiz yolları
  hazırlama alanına almak;
- belirsiz üretilmiş içerik, ikili dosya, şema veya ürün kararlarında tahmin yürütmek.

**Nasıl çağrılır:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### Depolar ve değişiklik teslimi

#### `synchronize-git-repositories`

Yerel çalışmanın üzerine yazmadan güncel uzak durumu belirleyin.

**Ne yapar:**

- yalnızca görevle ilgili depoları keşfeder ve izlenen uzak kaynaklarını getirir;
- yalnızca geride olan temiz dalları hızlı ileri alır;
- kirli, ileride, ayrışmış, ayrık HEAD, izlenmeyen ve devam eden işlem durumlarını
  bildirir;
- proje politikası gerektirdiğinde ilk düzenlemeden önce doğrulanmış güncel
  `main` üzerinden yetkilendirilmiş bir özellik dalını yayımlar.

**Ne yapmaz:**

- otomatik stash, reset, rebase, merge, clean, switch veya force-push yapmak;
- ayrışmayı gizlemek veya başarılı getirmeyi yerel dalın güncellendiğinin
  kanıtı saymak;
- ilgisiz depoları taramak veya güncellemek.

**Nasıl çağrılır:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Projenin bildirdiği kontrolleri gönderilecek kesin Git durumuna bağlayın.

**Ne yapar:**

- kurulu beceri klasörü dışında, depoya ait bir doğrulama politikası yapılandırır;
- bildirilen kontrolleri çalıştırır ve kesin commit'ler, çalışma ağaçları, üst
  kaynak durumu ve doğrulama yapılandırması için kanıt kaydeder;
- korunan kanıt eksik, başarısız, bozuk veya eskimişse işlemi güvenli biçimde durdurur.

**Ne yapmaz:**

- politika kapsamında olmayan ilgisiz depoları engellemek;
- rastgele kabuk komutlarını ayrıştırmak veya IDE'ye ya da ajana özgü kanca kurmak;
- eski bir Git durumunun başarılı kontrolünü güncel kanıt saymak.

**Nasıl çağrılır:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (deneysel)

Uygulama ile esas belgeler ayrı Git depolarındayken denetlenebilir tek bir
proje değişikliğini koordine edin.

**Ne yapar:**

- projenin bildirdiği uygulama ve belge deposu rollerini belirler;
- her iki başlangıç commit'ine ve esas belge kaynaklarına bağlı salt okunur plan
  oluşturur;
- gereksinimler, davranış, doğrulama, operasyonel etki ve sınırlamalar gibi
  yapılandırılmış konular için belge kanıtı gerektirir;
- ortak tamamlanma bildirmeden önce yayımlanmış her iki commit kimliğini,
  doğrulama kanıtını ve depolar arası izlenebilirliği doğrular.

**Ne yapmaz:**

- dizin veya depo adlarından depo rolleri çıkarmak;
- esas belgelerin yerine günlük özet koymak;
- kirli ve ayrışmış depolarda kendi başına düzenleme, commit, push, merge veya
  onarım yapmak;
- yalnızca beklenen belge dosyaları var diye anlamsal uyum iddia etmek.

**Nasıl çağrılır:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (deneysel)

Projenin bildirdiği GitFlow sözleşmesinden standart ve hotfix sürüm yollarını
yürütün.

**Ne yapar:**

- sürümlenmiş proje yapılandırmasından geliştirme, üretim, hotfix ad alanı,
  uzak kaynak, kontrol kapıları ve varsayılan yol politikasını belirler;
- kaynak commit'e ve uzak dal kimliklerine bağlı salt okunur planı dondurur;
- standart ve hotfix yollarına aynı bildirilmiş ortak kontrol kapılarını uygular;
- incelenmiş üretim yayımını, dağıtım kanıtını ve zorunlu hotfix'in geliştirme
  hattına yeniden entegrasyonunu doğrular.

**Ne yapmaz:**

- alışılmış dal adlarını varsaymak veya hotfix'i varsayılan yol olarak kullanmak;
- trunk tabanlı teslimi veya bu koleksiyonun özel sürüm zincirini desteklemek;
- korunan üretim dalına doğrudan göndermek, kontrol kapılarını atlamak, geçmişi
  yeniden yazmak veya ayrışmayı sessizce onarmak;
- yeniden entegrasyon doğrulanmadan üretim hotfix'ini tamamen bitmiş saymak.

**Nasıl çağrılır:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (deneysel)

Özellik hazırlığından incelenmiş geliştirme entegrasyonuna, teslim gözlemine,
belgelemeye ve kanıtlanmış temizliğe uzanan, projenin bildirdiği yolu planlayın
ve doğrulayın.

**Ne yapar:**

- düzenlemeden önce özet değerine bağlı bir planı dondurur ve saklanan kanıtlarla
  sıralı kontrol noktalarını ilerletir;
- depo kökleri, izlenen üst kaynaklar, kontroller ve belgeler gözlemlenebildiğinde
  yönetilen güncellemede veya ilk kullanımda temkinli bir proje yapılandırması
  oluşturur ve uyguladığı her varsayılanı bildirir;
- düzenleme öncesi özellik dalı, test önceliği, değişen kapsam ön kontrolü,
  inceleme, kesin durum gönderimi, işlem hattı, belgeler, geliştirme entegrasyonu,
  devredilmiş üretim, teslim, smoke testi, bildirim ve temizlik kapılarını doğrular;
- başarısızlıktan sonra bildirilmiş bir kontrol noktasına döner ve eskimiş sonraki
  adım kanıtlarını geçersiz kılar.

**Ne yapmaz:**

- proje kanıtı belirsiz olduğunda sağlayıcıya özgü bağdaştırıcıları, depo
  rollerini, teslim politikasını veya yetkilendirmeyi tahmin etmek;
- kendi başına gönderim yapmak, inceleme açmak ya da birleştirmek, dağıtmak,
  bildirmek, belgeleri düzenlemek veya kaynak silmek;
- üretim teslimini yürütmek; bu işlem `$execute-configured-gitflow-releases`
  gibi onaylı sürüm iş akışına devredilmiş olarak kalır.

Önce gerekli becerileri kurun ve yapılandırın: `$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push` ve
`$review-code-changes`. Projeye ait sürüm 1 yaşam döngüsü sözleşmesi eksikse ilk
plandan önce gözlemlenebilir proje olgularından başlatılır; proje daha belirgin
politika bildirdiğinde raporlanan varsayılanları inceleyip iyileştirin.
İsteğe bağlı becerileri yalnızca proje ilgili kontrol noktalarını
etkinleştirdiğinde kurun: `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram` ve
`$execute-configured-gitflow-releases`.

**Nasıl çağrılır:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### Proje bilgisi ve süreklilik

#### `maintain-work-log`

`docs/reports/work-log.md` konumunda esas tarihli proje günlüğünü tutun.

**Ne yapar:**

- önemli değişiklikleri, işlemleri, tanıları, kararları, doğrulamaları,
  engelleri ve geri alma sonuçlarını kaydeder;
- projenin mevcut günlük biçimini korur;
- eksik geçmişi mevcut Git ve proje görevi kanıtlarından yeniden oluşturur.

**Ne yapmaz:**

- proje politikası veya kullanıcı gerektirmedikçe olağan işlerde etkinleşmek;
- sırları, uygulama günlüklerini, zaman takibini veya kişisel notları yazmak;
- mevcut kanıtların destekleyemediği olayları iddia etmek.

**Nasıl çağrılır:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (deneysel)

Proje belgelerinde tamamlanan proje değişikliklerinin kullanıcıya yönelik
günlük özetini tutun.

**Ne yapar:**

- tamamlanan değişiklikleri bugünün tarihi altında yeni yetenekler,
  iyileştirmeler, düzeltmeler, güvenlik, belgeler veya önemli davranış
  değişiklikleri olarak gruplar;
- teknik olmayan kısa sonuçlar yazar ve boş kategorileri atlar;
- en yeni tarihleri başta tutar ve önceki her tarihi değiştirmeden bırakır;
- aynı gün birden fazla geliştiricinin güvenle katkıda bulunabilmesi için içeriğe
  bağlı plan, iş birliğine dayalı kilit, atomik değiştirme ve yineleme tespiti kullanır.

**Ne yapmaz:**

- proje açıkça belirtmiyorsa bir belge konumu seçmek veya oluşturmak;
- planları, başarısız deneyleri, dahili uygulama faaliyetlerini veya
  desteklenmeyen kullanıcı faydalarını kaydetmek;
- teknik çalışma günlüğünün, sürüm notlarının veya geleneksel değişiklik
  günlüğünün yerini almak;
- olağan aynı gün güncellemesinde geçmiş özet dönemlerini yeniden yazmak.

**Nasıl çağrılır:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Özel, hassas verilerden arındırılmış proje ve sohbet başına devam durumunu
bilgisayarlar arasında eşitleyin. Beceri, gerçek cihazlarda yapılan iki
bağımsız Google Drive çalışması deterministik yükseltme kapısını geçtikten
sonra kararlı hale gelmiştir.

**Ne yapar:**

- değişmez kontrol noktalarını onaylı eşitlenen klasörde veya bağlı Google
  Drive'da saklar; makineye özgü yapılandırmayı depo dışında tutar;
- mevcut arka ucu koruyarak ve yerel eşitlenen klasörü kullanmadan önce açık
  katılım gerektirerek, nitelenmemiş eşitleme isteklerinde varsayılan olarak
  bağlı Google Drive'ı kullanır;
- yeni bir bilgisayarda uzak klasör oluşturmadan önce depo parmak iziyle
  doğrulanmış mevcut Google Drive eşlemesini keşfeder; eksik listelemelerde,
  güvenilmeyen görünürlükte veya yinelenen eşleşmelerde işlemi engeller;
- proje görevi başına tek bir opak akış tutar: ayrıntılı başlangıç durumu
  ardından kısa farklar, görünen başlıkların tam metni, kararlar, doğrulama,
  açık sorular, sonraki adımlar ve Git parmak izleri;
- değişmemiş/etkin görevleri atlayıp çakışmaları açıkça göstererek tüm son ve
  sabitlenmiş proje görevlerini kaydeder, geri yükler veya çift yönlü planlar;
- indirilen anlık görüntüleri doğrular, yüklenenleri geri okur, projeler arası
  geri yüklemeyi önler ve yüksek güvenli gizli bilgi örüntülerini reddeder;
- bildirilen kurallar, beceriler, eklentiler ve Git'in zaten sağlamadığı güvenli
  skaler ayarlar için ayrı bir ortam manifesti kaydeder.

**Ne yapmaz:**

- kaynak dosyalarını, farkları, ham konuşma dökümlerini, gizli akıl yürütmeyi,
  kimlik bilgilerini, OAuth belirteçlerini veya beceri/eklenti kurulumlarını kopyalamak;
- Git'in zaten taşıdığı kuralları veya bağımlılıkları çoğaltmak;
- Git'e ait hedef kuralların üzerine sessizce yazmak: uygulama, açık bir plandan
  sonra yalnızca etkin ajan için seçilen eksik ve izlenmeyen bir `AGENTS.md`
  veya `CLAUDE.md` oluşturabilir;
- yalnızca meta veri modunda dal adlarını veya dosya yollarını dahil etmek;
  görünen görev başlıkları bilinçli olarak dahil kalır.

Codex Desktop belgelenmiş toplu görev keşfi, oluşturma, yeniden adlandırma ve
Google Drive bağlayıcısı iş akışlarını destekler. Claude Code taşınabilir
kontrol noktası, yerel klasör depolaması ve ortam uzlaştırma çekirdeğini
kullanabilir; ancak oturum deposu incelenmez ve yalnızca Codex'e özgü toplu
görev işlemleri desteklenmiyor olarak güvenli biçimde durdurulur.

**Nasıl çağrılır:**

Her bilgisayarı bir kez yapılandırın:

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

Ardından görev düzeyinde veya toplu komutlar kullanın; örneğin:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

Claude Code'da bu örneklerdeki `$` önekini `/` ile değiştirin.

### Koordinasyon ve iletişim

#### `orchestrate-agent-work` (deneysel)

Bütünleşik sonucun sorumluluğunu koruyarak açıkça yetkilendirilmiş alt ajanları
koordine edin.

**Ne yapar:**

- paralel çalışmayı sınırlı, örtüşmeyen görevlere böler;
- ajan sonuçlarını ortak kısıtlarla karşılaştırarak izler ve uzlaştırır;
- tamamlandığını bildirmeden önce birleşik sonucu doğrular.

**Ne yapmaz:**

- kullanıcı veya proje talimatları alt ajanlara izin vermedikçe iş devretmek;
- onay yetkisini, sırları, yıkıcı temizliği veya onaylanmamış harici
  değişiklikleri başka bir ajana aktarmak;
- bağımsız tamamlanan alt görevleri entegrasyonun başarılı olduğunun kanıtı saymak.

**Nasıl çağrılır:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (deneysel)

Her ekip üyesinin genel becerilerini incelenmiş tek bir manifestle uyumlu tutun;
proje yapılandırması yerel kalır.

**Ne yapar:**

- onaylı bir belge kökünde `team-agent-skills.md` oluşturur veya okur;
- bildirilen Codex ve Claude Code becerilerini doğrulanmış genel kopyalarla
  karşılaştırır;
- ortamı değiştirmeden eksik, eski, daha yeni, doğrulanmamış, proje geçersiz
  kılması ve korunan fazlalık durumlarını bildirir;
- sabitlenmiş tek bir koleksiyon sürümü için manifest özetine bağlı kurulum
  planı oluşturur;
- onaydan sonra yalnızca incelenmiş kümeyi kurar ve gözlemlenebilir durumu doğrular.

**Ne yapmaz:**

- bir iş istasyonunun rastlantısal durumunu otomatik olarak ekip politikasına
  dönüştürmek;
- sırları, kullanıcı yapılandırmasını, makine yollarını veya eklenti kimlik
  doğrulamasını saklamak;
- fazla becerileri kaldırmak, daha yeni kopyaları eski sürüme düşürmek veya
  eski proje kopyalarını onaysız silmek;
- çalışan bir ajan görevinin yeni kurulan becerileri yeniden yüklediğini iddia etmek.

**Nasıl çağrılır:**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `report-skill-feedback` (deneysel)

Açık onaydan sonra gözlemlenen bir beceri kullanımı hakkında sınırlı ve kimliksizleştirilmiş bir rapor hazırlar. Taslak kod, tam konuşmalar, sırlar, adlar, yollar veya URL’ler içermez. Tamamı gösterilir ve yalnızca ikinci bir onaydan sonra `kolabse/skills` deposuna gönderilir; GitHub issue gönderen hesaba bağlıdır ve anonim değildir.

**Aufruf / Invocation:**

```text
$report-skill-feedback Prepare a de-identified preview about this observed skill use; do not submit it yet.
```

#### `notify-via-telegram`

Uzun süren ajan görevleri için Telegram üzerinden yaşam döngüsü güncellemeleri gönderin.

**Ne yapar:**

- başlangıçları, kilometre taşlarını, ara sonuçları, sorunları, engelleri ve
  tamamlanmayı bildirir;
- botu etkileşimli olarak doğrular ve hedef sohbetin bulunmasına yardımcı olur;
- Windows'ta Codex Desktop için maskelenmiş, yapıştırmaya uygun ilk kullanım
  formu sağlar;
- kimlik bilgilerini kullanıcı yapılandırma dizininde saklar ve kurulum
  sırasında test bildirimi gönderir;
- genel-artı-proje teslimi ile yalnızca proje teslimi arasında açık seçimle,
  proje başına ayrı bir sohbeti veya forum konusunu destekler;
- `sync-project-context` ile uzlaştırılmak üzere sır içermeyen proje yönlendirme
  değerlerini dışa aktarır;
- Windows, macOS ve Linux'ta Python 3 standart kütüphanesiyle çalışır.

**Ne yapmaz:**

- bot belirtecini konuşmaya, kabuk geçmişine veya depoya yerleştirmek;
- genel bot belirtecini veya Telegram kimlik doğrulama durumunu bilgisayarlar
  arasında kopyalamak;
- kullanıcı ilerlemenin mevcut görevde kalmasını istediğinde bildirim göndermek;
- genel bir Telegram bot geliştirme çerçevesi olarak çalışmak.

**Nasıl çağrılır:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### Altyapı ve operasyonlar

#### `operate-yandex-cloud`

Açıkça yapılandırılmış, proje kapsamındaki Yandex Cloud altyapısını işletin.

**Ne yapar:**

- paylaşılan Cloud/Folder kimliklerini proje yapılandırmasında, iş istasyonunun
  `yc` profilini ise Git tarafından yok sayılan yerel yapılandırmada saklar;
- gerekli araç takımlarını algılar, asgari sürümleri denetler ve salt okunur
  bağlam ön kontrolü çalıştırır;
- kapsamı belirlenmiş CLI, SSH, Terraform, Ansible, Helm, Kubernetes, dağıtım,
  veritabanı, depolama, DNS, izleme, yedekleme ve olay iş akışlarını destekler;
- JSON çıktısı ve platformlar arası Python yardımcıları sağlar.

**Ne yapmaz:**

- sağlayıcı bağlamı olmadan genel SSH, Kubernetes, Terraform veya dağıtım
  isteklerinden Yandex Cloud sonucunu çıkarmak;
- kimlik bilgilerini paylaşılan proje yapılandırmasında saklamak;
- hedef, bağlam ve yetkilendirme belirlenmeden bir değişiklik uygulamak.

**Nasıl çağrılır:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### Beceri koleksiyonunun gelişimi

#### `discover-skill-candidates` (deneysel)

Beceri oluşturmadan, sınırlı proje ve bağlam kanıtlarında yeniden kullanılabilir
beceri fikirleri bulun.

**Ne yapar:**

- sınırlı, projeye göreli `AGENTS.md` dosyalarının envanterini Git ve satır
  düzeyinde köken bilgisiyle çıkarır;
- isteğe bağlı olarak proje belgelerini, seçilen dosyaları, sınırlı Git
  geçmişini, yapı meta verilerini ve mevcut sohbetlerden veya
  `sync-project-context` devirlerinden kullanıcıca onaylanmış özetleri
  envantere alır;
- adayları önerilen, araştırılacak veya reddedilen olarak sıralar ve mevcut
  kataloglarla karşılaştırır;
- uygun her adayı `kolabse/skills` için güvenli katkı, yerel oluşturma veya
  erteleme seçenekleriyle proaktif olarak sunar;
- seçilen fikri, bakım sorumlularının bağımsız doğrulayabileceği, hassas verilerden
  arındırılmış ve özet değerine bağlı bir katkı paketi olarak dışa aktarır.

**Ne yapmaz:**

- proje kurallarını değiştirmek veya beceri iskeleti oluşturmak, yayımlamak ya
  da kurmak;
- sohbetleri listelemek, ham konuşma dökümlerini almak veya kaynak kodunu geniş
  çapta taramak;
- ham kuralları, yerel yolları, sırları, URL'leri veya e-posta adreslerini
  dışa aktarmak;
- yalnızca politikadan ibaret, değişken, hassas veya tek seferlik kuralları
  incelemeden yeniden kullanılabilir iş akışları olarak öne çıkarmak.

**Nasıl çağrılır:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Deterministik beceri koleksiyonu sürümlerini planlayın, doğrulayın, denetleyin
ve temizliğini yapın.

**Ne yapar:**

- sürümleri, değişiklik günlüğünün hazırlığını, depo durumunu, testleri,
  güvenliği, deterministik arşivleri ve sağlama toplamlarını denetler;
- commit'e bağlı holdout, tüketici, platform, inceleme ve yerel kontrol
  kanıtlarını doğrular;
- değişmez GitHub varlıklarını, manifestleri, sağlama toplamlarını ve tasdikleri
  denetler;
- temizlikten önce geçici dalların birleştirildiğini, aynı ağaca sahip olduğunu
  veya yama açısından eşdeğer olduğunu kanıtlar;
- açıkça onaylanmış temizliği yalnızca değişmemiş güvenli bir plan ve yayımlanmış
  sürümün özet doğrulamasını geçen denetimi üzerinden uygular.

**Ne yapmaz:**

- commit, etiketleme, gönderim, iş akışı başlatma veya varlık yayımlama izni
  verildiğini varsaymak;
- mevcut etiketi taşımak veya yayımlanmış varlıkları değiştirmek;
- yalnızca adlardan, eski bir plandan veya denetlenmemiş bir sürümden yola
  çıkarak dal silmek.

**Nasıl çağrılır:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Desteklenen bileşimler

Katalog, yeniden kullanılabilir üç sıralı iş akışı tanımlar:

- `protected-push`: depoları eşitleyin, ardından güncel doğrulama kanıtı üretin;
  çalışma günlüğü ve Telegram bildirimi isteğe bağlıdır.
- `yandex-cloud-operation`: depoları eşitleyin, ardından kapsamı belirlenmiş
  bulut işlemini çalıştırın; doğrulama, çalışma günlüğü ve Telegram bildirimi,
  proje politikası etkinleştirdiğinde isteğe bağlıdır.
- `skill-collection-release`: depoyu eşitleyin, koleksiyon sürümünü planlayıp
  yerel olarak doğrulayın, ardından gönderim öncesi kanıtı bağlayın; çalışma
  günlüğü ve Telegram bildirimi isteğe bağlıdır.

Gerekli adımlar hata halinde işlemi durdurur. İsteğe bağlı günlük kaydı ve
bildirim, birincil işlemin gözlemlenen sonucunu değiştirmeden kendi
başarısızlıklarını bildirir. Kesin planı `scripts/compose_skills.py` ile
çözümleyin; adım sırasını, gerekli sonuçları ve engelleyici olmayan isteğe
bağlı başarısızlıkları doğrulamak için `schemas/composition-evidence.schema.json`
ile eşleşen, özet değerine bağlı belgeyle `--evidence` geçirin. Doğrulanmış
sonuç `schemas/composition-result.schema.json` şemasına uyar.

## Beceri ekleme

[CONTRIBUTING.md](CONTRIBUTING.md) belgesini izleyin ve
[`templates/skill-template.md`](../../../templates/skill-template.md) ile başlayın.
Her becerinin sahibini, platformlarını, durumunu, lisansını ve kökenini kaydeden
eşleşen bir `skill-catalog.json` kaydı olmalıdır. Güncellemelerin üzerine
yazamaması için projeye özgü yapılandırmayı kurulu beceri klasörü dışında tutun.

Tek bir beceri için depo düzeyinde kurucu eklemeyin. Koleksiyonun ChatGPT ve
Codex genelinde yönetilen kurulum ve güncellemelere ihtiyacı olduğunda bu
ajanlar arası düzene ek olarak koleksiyonu OpenAI eklentisi olarak paketleyin.

Koleksiyon kontrollerini yerel olarak çalıştırın:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Bir ajan veya model seçici için kör tetikleyici test paketi hazırlayın:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

Paket yalnızca beceri adlarını, herkese açık açıklamaları, opak örnek
kimliklerini ve istemleri içerir. Beklenen etiketleri ve yazar gerekçelerini
dışarıda bırakır. Seçici, her örnek için seçilen tüm becerileri listeleyen katı
JSON döndürür; gözlemleri şöyle puanlayın:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Paketi standart girdiden okuyup tahminleri standart çıktıya yazan seçiciyi
çağırmak için `run` ile `--` sonrasında bir komut kullanın. Sağlayıcı kimlik
bilgilerini komut bağımsız değişkenlerinin dışında tutun. Yok sayılan
`.trigger-evals/` dizini, üretilen paketleri, tahminleri ve raporları varsayılan
olarak commit'lerin dışında tutar. Uzun katı JSON yanıtları opak örnek
kimliklerini kesmesin diye büyük geliştirme paketleri varsayılan olarak özet
değerine bağlı 64 örneklik gruplar halinde gönderilir. Beklenen etiketleri
seçiciye göstermeden sınırı `--batch-size` ile ayarlayın.

Sürümden önce, geliştirme sırasında açıklamaları ayarlamak için kullanmadan,
ayrı sürümlenmiş ve özet değeri kilitli holdout'u çalıştırın:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Aday raporunu aynı holdout sürümü için üretilmiş raporla karşılaştırın:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

İddia özetleri farklıysa veya genel doğruluk, kesinlik, duyarlılık ya da
beceri başına bir metrik yapılandırılmış sınırların ötesinde düşerse
karşılaştırma güvenli biçimde başarısız olur. Varsayılan olarak
`skill-catalog.json` içinde adlandırılmış yayımlanmış temel raporu kullanır;
`--baseline` yalnızca başka bir uyumlu raporla bilinçli olarak karşılaştırırken
geçirilmelidir.

Deterministik olmayan model seçicilerinde en az üç olmak üzere tek sayıda kör
tahmin çalışması toplayın ve çoğunluk kararlarını puanlayın:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Bir sürümü doğrulama

Sürümlenmiş yayımlar deterministik ZIP ve TAR.GZ arşivlerini,
`release-manifest.json` ve `SHA256SUMS` içerir. Dört varlığın tümünü tek bir
dizine indirin ve şu komutla doğrulayın:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub ayrıca yüklenen her sürüm varlığı için SHA-256 `digest` sunar. Sürüm iş
akışları ek olarak GitHub çıktı tasdikleri yayımlar. İndirilen bir çıktıyı bu
depoya karşı doğrulayın:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
