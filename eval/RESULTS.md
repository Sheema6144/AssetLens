# Search evaluation results

_Generated 2026-10-04 20:13 from the Evaluate tab. Relevance judged manually by looking at each result._

| Metric | Value |
|---|---|
| Queries | 14 (fully judged: 14) |
| Mean Precision@5 | 0.886 |
| Mean Reciprocal Rank | 0.916 |
| Hit rate@5 (≥1 relevant in top 5) | 1.0 |
| Mean Recall@10 (vs. all assets judged relevant) | 0.976 |

## Per query

| # | Query | Detected type | P@5 | MRR | Latency |
|---|---|---|---|---|---|
| 1 | a woman standing with a cat | - | 1.0 | 1.0 | 2307 ms |
| 2 | customer testimonial videos | video | 0.8 | 1.0 | 1421 ms |
| 3 | brochures related to residential projects | pdf | 0.6 | 0.5 | 916 ms |
| 4 | images showing a modern living room | image | 1.0 | 1.0 | 575 ms |
| 5 | videos containing construction activity | video | 1.0 | 1.0 | 692 ms |
| 6 | people in a business meeting | - | 1.0 | 1.0 | 506 ms |
| 7 | aerial view of a city at night | - | 1.0 | 1.0 | 821 ms |
| 8 | food served on a table | - | 1.0 | 1.0 | 1019 ms |
| 9 | a dog playing outdoors | - | 1.0 | 1.0 | 1605 ms |
| 10 | beach at sunset | - | 1.0 | 1.0 | 2364 ms |
| 11 | apartment floor plan | - | 1.0 | 1.0 | 2636 ms |
| 12 | construction site photos | image | 1.0 | 1.0 | 3342 ms |
| 13 | a red car parked on the street | - | 0.6 | 0.33 | 3503 ms |
| 14 | two cats sleeping together | - | 0.4 | 1.0 | 3402 ms |

### 1. “a woman standing with a cat”

- **User is trying to find:** Photos (or clips) where a woman and a cat appear together.
- **Expected assets:** Images from the 'woman cat' download batch; NOT photos of cats alone or women alone.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_6647719.jpg` | image | 3.87 | image: a woman holding a cat in her arms | ✅ |
| 2 | `pixabay_img_4504156.jpg` | image | 3.851 | image: a woman holding a cat in her arms | ✅ |
| 3 | `pixabay_img_6687637.jpg` | image | 3.815 | image: a woman sitting on a chair holding a cat | ✅ |
| 4 | `pixabay_img_7445834.jpg` | image | 3.748 | image: a woman in a black dress holding a white cat | ✅ |
| 5 | `pixabay_img_5007178.jpg` | image | 3.719 | image: a woman holding a white cat in her arms | ✅ |

**Observations:** _(none)_

### 2. “customer testimonial videos”

- **User is trying to find:** Videos of a person speaking to the camera / giving a review.
- **Expected assets:** Talking-head / interview videos (speech transcript + 'person talking to camera' frames).
- **Result:** P@5 = 0.8, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `commons_vid_180626791.webm` | video | 4.786 | frame @ 48s:  | ✅ |
| 2 | `commons_vid_141404434.webm` | video | 4.746 | frame @ 52s:  | ✅ |
| 3 | `commons_vid_141404274.webm` | video | 4.447 | frame @ 119s:  | ✅ |
| 4 | `commons_doc_91606518.pdf` | pdf | 4.155 | pdf_text p.59: 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 MR. DAVIS: Tha | ❌ |
| 5 | `commons_vid_141404453.webm` | video | 4.136 | frame @ 201s:  | ✅ |

**Observations:** _(none)_

### 3. “brochures related to residential projects”

- **User is trying to find:** PDF brochures that market housing / apartments / residential developments.
- **Expected assets:** Residential brochures (generated + Wikimedia), not office or tourism brochures.
- **Result:** P@5 = 0.6, MRR = 0.5

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `doc_1007.pdf` | pdf | 4.443 | pdf_text p.2: BuildRight Construction Services - highlights Foundations, structural work, proj | ❌ |
| 2 | `doc_1001.pdf` | pdf | 3.896 | pdf_text p.3: Green Meadows Residences - highlights RERA approved housing project. | ✅ |
| 3 | `commons_doc_152958771.pdf` | pdf | 3.818 | pdf_text p.1: by Matthew C. Godfrey and Paul Sadin with Dawn Vogel, Joshua Pollarine, and Nico | ✅ |
| 4 | `commons_doc_152937381.pdf` | pdf | 3.581 | pdf_text p.2: Process Throughout project delivery, the public is kept informed through public  | ❌ |
| 5 | `doc_1005.pdf` | pdf | 3.536 | pdf_text p.2: Riverside Township Phase II - highlights Plotted development and row houses with | ✅ |

**Observations:** _(none)_

### 4. “images showing a modern living room”

- **User is trying to find:** Interior photos of contemporary living rooms.
- **Expected assets:** Living-room interior photos; kitchens/bedrooms are partial matches.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_998265.jpg` | image | 5.369 | image: a modern living room with white furniture and wood flooring | ✅ |
| 2 | `pixabay_img_1851201.jpg` | image | 5.114 | image: a living room with a couch, chair and table | ✅ |
| 3 | `pixabay_img_9053405.jpg` | image | 5.04 | image: a living room with a couch and a coffee table | ✅ |
| 4 | `pixabay_img_1622401.jpg` | image | 5.0 | image: a living room with a couch and a glass coffee table | ✅ |
| 5 | `pixabay_img_2685521.jpg` | image | 4.985 | image: a living room with a couch, chair and stairs | ✅ |

**Observations:** _(none)_

### 5. “videos containing construction activity”

- **User is trying to find:** Video clips of construction sites, cranes, excavators, workers.
- **Expected assets:** Construction / crane / excavator videos with the matching keyframe timestamp.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_vid_41826.mp4` | video | 5.122 | frame @ 0s: a construction site in the middle of a residential area | ✅ |
| 2 | `pixabay_vid_42923.mp4` | video | 5.048 | frame @ 12s: aerial view of construction site | ✅ |
| 3 | `pixabay_vid_42926.mp4` | video | 4.977 | frame @ 0s: a construction site in the middle of a city | ✅ |
| 4 | `pixabay_vid_40298.mp4` | video | 4.892 | frame @ 20s: a large pile of gravel next to a building | ✅ |
| 5 | `pixabay_vid_199375.mp4` | video | 4.473 | frame @ 4s: an aerial view of a construction site | ✅ |

**Observations:** _(none)_

### 6. “people in a business meeting”

- **User is trying to find:** Office meeting scenes (images or videos).
- **Expected assets:** Meeting / office teamwork photos and clips.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_5395615.jpg` | image | 4.668 | image: a group of business people sitting at a table in a meeting room | ✅ |
| 2 | `pixabay_img_10209984.jpg` | image | 4.43 | image: a group of people sitting around a table in a meeting room | ✅ |
| 3 | `pixabay_img_10186537.jpg` | image | 4.289 | image: a group of business people sitting around a conference table | ✅ |
| 4 | `pixabay_img_10234773.jpg` | image | 4.147 | image: a group of people sitting around a conference table | ✅ |
| 5 | `pixabay_img_1979261.jpg` | image | 4.053 | image: a group of business people sitting around a table | ✅ |

**Observations:** _(none)_

### 7. “aerial view of a city at night”

- **User is trying to find:** Drone / skyline shots of a city after dark.
- **Expected assets:** Night city aerials; daytime aerials are only partially relevant.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_4335245.jpg` | image | 4.405 | image: an aerial view of a city at night | ✅ |
| 2 | `pixabay_img_6528401.jpg` | image | 4.292 | image: an aerial view of a city at night | ✅ |
| 3 | `pixabay_vid_336755.mp4` | video | 4.259 | frame @ 8s: an aerial view of a city at night | ✅ |
| 4 | `pixabay_vid_2860.mp4` | video | 4.218 | frame @ 46s: an aerial view of a city at night | ✅ |
| 5 | `pixabay_img_5644601.jpg` | image | 4.109 | image: a view of a city at night | ✅ |

**Observations:** _(none)_

### 8. “food served on a table”

- **User is trying to find:** Food photography / dining scenes.
- **Expected assets:** Food and restaurant images and cooking clips.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1050813.jpg` | image | 4.423 | image: a wooden table topped with plates of food | ✅ |
| 2 | `pixabay_img_2009590.jpg` | image | 4.329 | image: a table full of food and wine | ✅ |
| 3 | `pixabay_img_4234067.jpg` | image | 3.801 | image: a white table topped with breakfast foods on it | ✅ |
| 4 | `pixabay_img_449952.jpg` | image | 3.783 | image: a table set for a dinner in a restaurant | ✅ |
| 5 | `pixabay_img_4809593.jpg` | image | 3.751 | image: a bowl of food sitting on a wooden table | ✅ |

**Observations:** _(none)_

### 9. “a dog playing outdoors”

- **User is trying to find:** Dogs running or playing outside.
- **Expected assets:** Dog photos/videos in parks, beaches, gardens.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_750555.jpg` | image | 3.737 | image: a dog playing with a yellow ball in the grass | ✅ |
| 2 | `pixabay_img_750554.jpg` | image | 3.717 | image: a dog playing with a yellow ball in the grass | ✅ |
| 3 | `pixabay_img_9830833.jpg` | image | 3.561 | image: a small dog is playing in the snow | ✅ |
| 4 | `pixabay_img_6510806.jpg` | image | 3.444 | image: a small dog running through a lush green field | ✅ |
| 5 | `pixabay_img_7447065.jpg` | image | 3.444 | image: a small dog running through a grassy field | ✅ |

**Observations:** _(none)_

### 10. “beach at sunset”

- **User is trying to find:** Seaside scenes at dusk.
- **Expected assets:** Beach + sunset images and ocean clips.
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1637376.jpg` | image | 4.404 | image: a beach at sunset with waves coming in the sand | ✅ |
| 2 | `pixabay_img_9280759.jpg` | image | 4.293 | image: a pier on the beach at sunset | ✅ |
| 3 | `pixabay_img_9319305.jpg` | image | 4.163 | image: the sun setting over the ocean at the beach | ✅ |
| 4 | `pixabay_img_1751455.jpg` | image | 4.145 | image: a beach with waves crashing on the sand at sunset | ✅ |
| 5 | `pixabay_vid_4006.mp4` | video | 4.132 | frame @ 34s:  | ✅ |

**Observations:** _(none)_

### 11. “apartment floor plan”

- **User is trying to find:** Documents or images containing architectural floor plans.
- **Expected assets:** Brochure pages with floor plans (matched page number shown).
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_354233.jpg` | image | 3.091 | image: a drawing of a house on top of a blueprint | ✅ |
| 2 | `pixabay_img_2094666.jpg` | image | 3.046 | image: a kitchen and dining area in a modern apartment | ✅ |
| 3 | `pixabay_img_7124141.jpg` | image | 2.673 | image: an apartment building with bales and bales bales bales bales bales bales bales b | ✅ |
| 4 | `pixabay_img_2014863.jpg` | image | 2.624 | image: a living room and kitchen area with hardwood flooring | ✅ |
| 5 | `doc_1002.pdf` | pdf | 2.525 | pdf_text p.3: Skyline Heights Apartments - highlights Book your dream home today.. | ✅ |

**Observations:** _(none)_

### 12. “construction site photos”

- **User is trying to find:** Still images (not videos) of construction work.
- **Expected assets:** Construction images ranked above construction videos (type intent = image).
- **Result:** P@5 = 1.0, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_4121483.jpg` | image | 5.559 | image: a construction site in the middle of a city | ✅ |
| 2 | `pixabay_img_6778044.jpg` | image | 5.17 | image: construction cranes at a construction site | ✅ |
| 3 | `pixabay_img_7277918.jpg` | image | 5.156 | image: a construction site with a crane in the background | ✅ |
| 4 | `pixabay_img_6705863.jpg` | image | 5.13 | image: construction workers working on a building site | ✅ |
| 5 | `pixabay_img_4020496.jpg` | image | 5.126 | image: construction workers at a construction site | ✅ |

**Observations:** _(none)_

### 13. “a red car parked on the street”

- **User is trying to find:** Fine-grained attribute query (colour + object + context).
- **Expected assets:** Street/car images; expected weakness: colour attribute may be ignored.
- **Result:** P@5 = 0.6, MRR = 0.33

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_6529013.jpg` | image | 5.424 | image: a red car parked on the side of a road | ❌ |
| 2 | `pixabay_img_6529011.jpg` | image | 5.015 | image: a red car parked on the side of the road | ❌ |
| 3 | `pixabay_img_1846910.jpg` | image | 4.947 | image: a red car parked on the side of a street | ✅ |
| 4 | `pixabay_img_6306695.jpg` | image | 4.793 | image: a red sports car parked on the side of a street | ✅ |
| 5 | `pixabay_img_2599492.jpg` | image | 4.753 | image: a red car parked on the side of a road | ✅ |

**Observations:** _(none)_

### 14. “two cats sleeping together”

- **User is trying to find:** Counting + action query.
- **Expected assets:** Expected weakness: CLIP is poor at counting, single cats will appear.
- **Result:** P@5 = 0.4, MRR = 1.0

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_4655521.jpg` | image | 4.364 | image: a cat sleeping on top of a couch | ✅ |
| 2 | `pixabay_img_4655518.jpg` | image | 4.24 | image: a cat laying on top of another cat | ✅ |
| 3 | `pixabay_img_5120490.jpg` | image | 3.977 | image: two cats sitting next to each other cats | ❌ |
| 4 | `pixabay_img_7140980.jpg` | image | 3.949 | image: two cats sitting next to each other cats | ❌ |
| 5 | `pixabay_vid_39009.mp4` | video | 3.815 | frame @ 4s: two cats laying on top of each other cats | ❌ |

**Observations:** _(none)_
