# デザイン素材

- hiraizumi-logo-medium-lotus.png：現行ヘッダーロゴ。大きくしたハスを少し縮小。組み込み `image_gen` で生成。2171 × 724 px、RGBA。

- hiraizumi-logo-large-lotus.png：旧版のヘッダーロゴ。細めの筆文字に合わせ、右側のハスを大きくした透過素材。2172 × 724 px、RGBA。組み込み `image_gen` で生成。

- spring-header.png：組み込みimage_genで生成。若葉・木漏れ日・柔らかな光、中央を緑の余白とした横長背景。指示：Bright fresh spring yellow-green leaves at upper corners, luminous bokeh, green center for white title, no text or logos.
- hiraizumi-logo-thin.png：筆文字の線をさらに細くした旧ロゴ。組み込み `image_gen` で旧ロゴを参照して生成。2172 × 724 px、RGBA。ヘッダーに使用。
- hiraizumi-logo.png：採用された筆文字とハスの見本から、組み込み `image_gen` で背景透過版を生成。2172 × 724 px、RGBA。旧版として保持。現行ロゴの代替テキストも「平泉の細道」。
- lotus-watercolor.png：同じ見本の淡いピンクのハスを、組み込み `image_gen` で単独の透過素材として生成。1448 × 1086 px、RGBA。ログイン・ユーザー登録画面に使用。
- lotus.svg：旧デザインの素材として保持。現在の画面からは参照しない。
- 見出し・仏の言葉：[Zen Maru Gothic](https://fonts.google.com/specimen/Zen+Maru+Gothic)、太さ900。Google Fontsから配信し、取得できない場合は端末の丸ゴシック等に代替。
- タイトル：丸みのある筆文字、小さめの「の」、やや細めの線と控えめなかすれの画像ロゴ。画像生成による透過化のため、見本とは細部が異なる場合がある。キャッチコピーには引き続き Yuji Syuku を使用。

## 透過素材の生成指示

### hiraizumi-logo-medium-lotus.png（現行）

参照：`hiraizumi-logo-large-lotus.png`。組み込み `image_gen` の最終プロンプト：

```text
Make one small localized edit to this transparent logo: reduce ONLY the entire lotus illustration at right (pink flower, stem, leaves and detached petal) to 85 percent of its current width and height, anchored around its current center. Keep the Japanese lettering 平泉の細道 completely unchanged in shape, size, placement, stroke thickness, color and texture. Keep the exact lotus artwork and colors, just slightly smaller. Same 2172x724 canvas and transparent RGBA background. No repositioning or scaling of the text or canvas. Preserve comfortable separation between the flower and the end of 道. No new elements, no background, no checkerboard.
```

### hiraizumi-logo-large-lotus.png

参照：`hiraizumi-logo-thin.png`。最終プロンプト：

```text
Edit this approved transparent website logo, enlarging ONLY the pink lotus illustration on the right to approximately 1.4 times its current width and height. Preserve its exact watercolor design, pale pink petals, green stem and leaves and detached pink petal. Keep the Japanese lettering 平泉の細道, thin stroke weight, brush texture, rounded shapes and ivory color unchanged. Keep comfortable separation from the lettering including the sweeping end of 道. You may extend the transparent canvas to the right as necessary to fit the larger flower without cropping or overlapping any strokes; do not shrink or redraw the lettering to make room. The lotus should be noticeably larger and balanced beside the title. Maintain a wide horizontal logo layout with small safe transparent margins. Genuine RGBA transparent background, no checkerboard, no additional text.
```

### hiraizumi-logo-thin.png

参照：`hiraizumi-logo.png`。組み込み `image_gen` の最終プロンプト：

```text
Edit this transparent website logo: make ONLY the Japanese brush lettering 平泉の細道 visibly thinner, reducing stroke widths by approximately 25 percent, while retaining each character's overall height, placement, rounded friendly shapes, small の, and graceful sweep lengths. Open up the counters and internal spaces. Keep natural gentle stroke contrast and just a little dry-brush texture at the tips. Warm ivory-white lettering should be mostly solid, with no gray outline or embossed shading. Preserve the existing pink lotus flower, stem, leaves and detached petal at right exactly, including their size and position. Preserve composition, aspect ratio, and generous safe margins. Genuine transparent alpha background, no opaque fill, no checkerboard. All five characters must read accurately 平泉の細道. This is a lighter-weight version of the same approved logo, not a different typeface.
```

参照画像：チャットで採用された `exec-c304dce6-98db-4116-bf4b-8c74844ae229.png`。以下は組み込み `image_gen` に渡した最終プロンプト。

### hiraizumi-logo.png

```text
Background extraction for production website logo. Extract the EXACT approved warm white Japanese calligraphy 平泉の細道 together with the pink lotus, stem, green leaves and detached petal at its right from the input image. Preserve the exact existing stroke shapes, weights, small の, texture, dry-brush tips, spacing, colors and relative lotus placement. This is NOT a redesign and NOT a new lettering variant. Remove ALL photographic green background, foliage and bokeh, replacing them with genuinely transparent alpha. No opaque color, no checkerboard drawn into image, no shadow halo. Tight wide landscape canvas bounding the complete lettering and lotus, with only 3 percent clear padding. All five characters must remain intact and legible. Deliver one high resolution RGBA transparent PNG logo cutout.
```

### lotus-watercolor.png

```text
Extract ONLY the small pale pink lotus flower illustration at the right of this reference image for a website icon. Keep the same delicate pale pink and cream petals, fine watercolor shading, green stem, two small green leaves, and detached pink petal to the right, with identical arrangement and style. Remove all Japanese lettering and all photographic background. Genuinely transparent alpha background, no checkerboard drawing, no opaque fill, no text. Single lotus illustration centered and filling a compact landscape 4:3 canvas with 5 percent transparent padding. Clean edges without green background halo. This is a faithful extraction of the existing lotus, not a redesign.
```
