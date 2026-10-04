# Search evaluation results

_Generated 2026-10-04 15:44 from the Evaluate tab. Relevance judged manually by looking at each result._

| Metric | Value |
|---|---|
| Queries | 14 (fully judged: 0) |
| Mean Precision@5 | None |
| Mean Reciprocal Rank | None |
| Hit rate@5 (≥1 relevant in top 5) | None |
| Mean Recall@10 (vs. all assets judged relevant) | None |

## Per query

| # | Query | Detected type | P@5 | MRR | Latency |
|---|---|---|---|---|---|
| 1 | a woman standing with a cat | - | n/j | n/j | 837 ms |
| 2 | customer testimonial videos | video | n/j | n/j | 710 ms |
| 3 | brochures related to residential projects | pdf | n/j | n/j | 908 ms |
| 4 | images showing a modern living room | image | n/j | n/j | 693 ms |
| 5 | videos containing construction activity | video | n/j | n/j | 613 ms |
| 6 | people in a business meeting | - | n/j | n/j | 733 ms |
| 7 | aerial view of a city at night | - | n/j | n/j | 502 ms |
| 8 | food served on a table | - | n/j | n/j | 310 ms |
| 9 | a dog playing outdoors | - | n/j | n/j | 500 ms |
| 10 | beach at sunset | - | n/j | n/j | 265 ms |
| 11 | apartment floor plan | - | n/j | n/j | 212 ms |
| 12 | construction site photos | image | n/j | n/j | 169 ms |
| 13 | a red car parked on the street | - | n/j | n/j | 174 ms |
| 14 | two cats sleeping together | - | n/j | n/j | 216 ms |

### 1. “a woman standing with a cat”

- **User is trying to find:** Photos (or clips) where a woman and a cat appear together.
- **Expected assets:** Images from the 'woman cat' download batch; NOT photos of cats alone or women alone.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `copy_pixabay_img_6647719.jpg` | image | 4.095 | image: a woman holding a cat in her arms | – |
| 2 | `pixabay_img_4504156.jpg` | image | 4.087 | image: a woman holding a cat in her arms | – |
| 3 | `pixabay_img_6687637.jpg` | image | 4.05 | image: a woman sitting on a chair holding a cat | – |
| 4 | `pixabay_img_3038253.jpg` | image | 3.874 | image: a woman holding a cat in her arms | – |
| 5 | `pixabay_img_7639862.jpg` | image | 3.848 | image: a woman holding a cat in her arms | – |

**Observations:** _(none)_

### 2. “customer testimonial videos”

- **User is trying to find:** Videos of a person speaking to the camera / giving a review.
- **Expected assets:** Talking-head / interview videos (speech transcript + 'person talking to camera' frames).

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `commons_vid_141404434.webm` | video | 4.325 | frame @ 52s:  | – |
| 2 | `commons_doc_80484309.pdf` | pdf | 4.306 | caption: the flyer for the seminar | – |
| 3 | `commons_vid_141404453.webm` | video | 3.69 | frame @ 201s:  | – |
| 4 | `doc_1009.pdf` | pdf | 2.606 | pdf_text p.2: Fresh Bites Restaurant Menu - highlights Catering available for corporate events | – |
| 5 | `pixabay_vid_131638.mp4` | video | 2.464 | frame @ 4s: a blue sky with the words thanks for warning | – |

**Observations:** _(none)_

### 3. “brochures related to residential projects”

- **User is trying to find:** PDF brochures that market housing / apartments / residential developments.
- **Expected assets:** Residential brochures (generated + Wikimedia), not office or tourism brochures.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `doc_1007.pdf` | pdf | 3.949 | pdf_text p.2: BuildRight Construction Services - highlights Foundations, structural work, proj | – |
| 2 | `doc_1001.pdf` | pdf | 3.298 | pdf_text p.3: Green Meadows Residences - highlights RERA approved housing project. | – |
| 3 | `doc_1005.pdf` | pdf | 3.066 | pdf_text p.2: Riverside Township Phase II - highlights Plotted development and row houses with | – |
| 4 | `doc_1003.pdf` | pdf | 2.63 | pdf_text p.2: Palm Grove Villas - highlights Private gardens, Italian marble flooring, smart-h | – |
| 5 | `pixabay_vid_41826.mp4` | video | 2.25 | frame @ 0s: a construction site in the middle of a residential area | – |

**Observations:** _(none)_

### 4. “images showing a modern living room”

- **User is trying to find:** Interior photos of contemporary living rooms.
- **Expected assets:** Living-room interior photos; kitchens/bedrooms are partial matches.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_9053405.jpg` | image | 4.351 | image: a living room with a couch and a coffee table | – |
| 2 | `pixabay_img_1622401.jpg` | image | 4.309 | image: a living room with a couch and a glass coffee table | – |
| 3 | `pixabay_img_2685521.jpg` | image | 4.302 | image: a living room with a couch, chair and stairs | – |
| 4 | `pixabay_img_2732939.jpg` | image | 4.183 | image: a living room with white brick walls and wooden floors | – |
| 5 | `pixabay_img_1835923.jpg` | image | 4.115 | image: a living room with a couch and a painting on the wall | – |

**Observations:** _(none)_

### 5. “videos containing construction activity”

- **User is trying to find:** Video clips of construction sites, cranes, excavators, workers.
- **Expected assets:** Construction / crane / excavator videos with the matching keyframe timestamp.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_vid_41826.mp4` | video | 4.152 | frame @ 0s: a construction site in the middle of a residential area | – |
| 2 | `pixabay_vid_42923.mp4` | video | 4.095 | frame @ 12s: aerial view of construction site | – |
| 3 | `pixabay_vid_42926.mp4` | video | 4.01 | frame @ 0s: a construction site in the middle of a city | – |
| 4 | `pixabay_vid_40298.mp4` | video | 3.908 | frame @ 20s: a large pile of gravel next to a building | – |
| 5 | `pixabay_vid_199375.mp4` | video | 3.561 | frame @ 4s: an aerial view of a construction site | – |

**Observations:** _(none)_

### 6. “people in a business meeting”

- **User is trying to find:** Office meeting scenes (images or videos).
- **Expected assets:** Meeting / office teamwork photos and clips.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1979261.jpg` | image | 4.004 | image: a group of business people sitting around a table | – |
| 2 | `pixabay_img_2284501.jpg` | image | 3.223 | image: a group of people sitting around a table | – |
| 3 | `pixabay_img_5382501.jpg` | image | 3.175 | image: a group of people sitting around a table with laptops | – |
| 4 | `pixabay_img_594091.jpg` | image | 3.044 | image: a group of people sitting at a table with laptops | – |
| 5 | `doc_1006.pdf` | pdf | 3.033 | caption: a group of people sitting around a table | – |

**Observations:** _(none)_

### 7. “aerial view of a city at night”

- **User is trying to find:** Drone / skyline shots of a city after dark.
- **Expected assets:** Night city aerials; daytime aerials are only partially relevant.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_2178705.jpg` | image | 3.567 | image: a city at night from the top of a building | – |
| 2 | `pixabay_img_2278471.jpg` | image | 3.516 | image: an aerial view of a busy intersection at night | – |
| 3 | `pixabay_img_9456745.jpg` | image | 3.405 | image: the tokyo skyline at night | – |
| 4 | `pixabay_img_1767540.jpg` | image | 3.296 | image: the city skyline at night in dubai, uae | – |
| 5 | `pixabay_img_4534092.jpg` | image | 3.146 | image: a view of the city from the top of a building | – |

**Observations:** _(none)_

### 8. “food served on a table”

- **User is trying to find:** Food photography / dining scenes.
- **Expected assets:** Food and restaurant images and cooking clips.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1050813.jpg` | image | 4.175 | image: a wooden table topped with plates of food | – |
| 2 | `pixabay_img_2009590.jpg` | image | 4.083 | image: a table full of food and wine | – |
| 3 | `doc_1009.pdf` | pdf | 3.912 | caption: a wooden table topped with plates of food | – |
| 4 | `pixabay_img_4234067.jpg` | image | 3.577 | image: a white table topped with breakfast foods on it | – |
| 5 | `pixabay_img_4809593.jpg` | image | 3.538 | image: a bowl of food sitting on a wooden table | – |

**Observations:** _(none)_

### 9. “a dog playing outdoors”

- **User is trying to find:** Dogs running or playing outside.
- **Expected assets:** Dog photos/videos in parks, beaches, gardens.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `doc_1010.pdf` | pdf | 3.886 | caption: a dog is playing in the snow | – |
| 2 | `pixabay_img_9830833.jpg` | image | 3.464 | image: a small dog is playing in the snow | – |
| 3 | `pixabay_img_8637542.jpg` | image | 3.302 | image: a small dog running across a lush green field | – |
| 4 | `pixabay_img_5671778.jpg` | image | 3.187 | image: a small white dog running through the grass | – |
| 5 | `pixabay_img_7087887.jpg` | image | 3.057 | image: a woman is playing with a dog in a field | – |

**Observations:** _(none)_

### 10. “beach at sunset”

- **User is trying to find:** Seaside scenes at dusk.
- **Expected assets:** Beach + sunset images and ocean clips.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1637376.jpg` | image | 4.343 | image: a beach at sunset with waves coming in the sand | – |
| 2 | `pixabay_img_9280759.jpg` | image | 4.24 | image: a pier on the beach at sunset | – |
| 3 | `pixabay_img_3726030.jpg` | image | 3.987 | image: a beautiful sunset over the ocean with waves and clouds | – |
| 4 | `pixabay_img_1850059.jpg` | image | 3.888 | image: a beautiful sunset over the ocean with rocks in the fore | – |
| 5 | `pixabay_img_5383043.jpg` | image | 3.712 | image: the sun is setting over the ocean at the beach | – |

**Observations:** _(none)_

### 11. “apartment floor plan”

- **User is trying to find:** Documents or images containing architectural floor plans.
- **Expected assets:** Brochure pages with floor plans (matched page number shown).

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_7124141.jpg` | image | 2.432 | image: an apartment building with bales and bales bales bales bales bales bales bales b | – |
| 2 | `doc_1002.pdf` | pdf | 2.396 | pdf_text p.3: Skyline Heights Apartments - highlights Book your dream home today.. | – |
| 3 | `pixabay_img_2437446.jpg` | image | 2.33 | image: a blackboard with white lines on it | – |
| 4 | `doc_1005.pdf` | pdf | 2.31 | pdf_text p.2: Riverside Township Phase II - highlights Plotted development and row houses with | – |
| 5 | `pixabay_img_1845884.jpg` | image | 2.298 | image: an apartment building with many windows and bals | – |

**Observations:** _(none)_

### 12. “construction site photos”

- **User is trying to find:** Still images (not videos) of construction work.
- **Expected assets:** Construction images ranked above construction videos (type intent = image).

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_4020496.jpg` | image | 4.143 | image: construction workers at a construction site | – |
| 2 | `pixabay_img_3555550.jpg` | image | 3.941 | image: a building under construction with scr scr scr scr scr scr scr scr scr scr scr s | – |
| 3 | `pixabay_img_2739233.jpg` | image | 3.932 | image: a group of construction workers standing around a construction site | – |
| 4 | `pixabay_img_4686908.jpg` | image | 3.817 | image: a group of construction workers working on a construction site | – |
| 5 | `pixabay_img_4754309.jpg` | image | 3.774 | image: a man in a construction site looking at a crane | – |

**Observations:** _(none)_

### 13. “a red car parked on the street”

- **User is trying to find:** Fine-grained attribute query (colour + object + context).
- **Expected assets:** Street/car images; expected weakness: colour attribute may be ignored.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_1846910.jpg` | image | 4.863 | image: a red car parked on the side of a street | – |
| 2 | `pixabay_img_8235289.jpg` | image | 4.584 | image: a red car parked on a cobb road | – |
| 3 | `pixabay_img_4333567.jpg` | image | 4.392 | image: a red car parked in front of a building | – |
| 4 | `pixabay_img_3335042.jpg` | image | 3.946 | image: a red car parked in front of a yellow building | – |
| 5 | `pixabay_img_5989090.jpg` | image | 3.834 | image: a small car parked on the side of the road | – |

**Observations:** _(none)_

### 14. “two cats sleeping together”

- **User is trying to find:** Counting + action query.
- **Expected assets:** Expected weakness: CLIP is poor at counting, single cats will appear.

| Rank | File | Type | Score | Why it matched | Relevant? |
|---|---|---|---|---|---|
| 1 | `pixabay_img_8105667.jpg` | image | 3.606 | image: two kittens are walking in the grass | – |
| 2 | `doc_1010.pdf` | pdf | 3.435 | caption: a cat laying down on a white surface | – |
| 3 | `pixabay_img_7965411.jpg` | image | 3.119 | image: a kitten laying on a bed with an orange blanket | – |
| 4 | `pixabay_img_1561948.jpg` | image | 3.104 | image: a black and white photo of a cat | – |
| 5 | `copy_pixabay_img_1192026.jpg` | image | 2.905 | image: a kitten laying down on a white surface | – |

**Observations:** _(none)_
