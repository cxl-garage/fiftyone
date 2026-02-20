## Notes on `fiftyone` objects
`fo.Dataset` consists of multiple `fo.Sample` objects, each of which represents an image. Each `fo.Sample` object has a `fo.Detections` object, which is a list of `fo.Detection` objects for an image.

### Dataset
`fo.Dataset` is defined at [fiftyone/fiftyone/core/dataset.py#L271](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/dataset.py#L271):
```python
    dataset = fo.Dataset("dataset_name", persistent=True) # stores the dataset at ~/.fiftyone/var/lib/mongo
    dataset = fo.load_dataset("dataset_name") # loads the dataset from ~/.fiftyone/var/lib/mongo
```

### Sample
`fo.Sample` is defined at [fiftyone/fiftyone/core/sample.py#L493](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/sample.py#L493):
```python
    sample = fo.Sample(filepath=cloud_path) # create the sample for an image at the given path, currently supported path formats: local path, http://,  https://, or gs://
    sample["annotations"] = fo.Detections(detections=detections) # adding detections
```

A `Sample` instance delegates data storage to an internal `_doc` object called the backing document. It holds the actual field values (filepath, tags, metadata, etc.) and handles serialization (converting Python objects to/from BSON dicts) and persistence (writing to MongoDB). `Sample` itself is a thin wrapper that proxies reads/writes to `_doc`.

The backing document classes are defined at [fiftyone/fiftyone/core/odm/sample.py](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/odm/sample.py). There are two:

| Class | When used | Storage |
|---|---|---|
| `NoDatasetSampleDocument` | Sample exists in memory only | Plain `OrderedDict` in RAM that is not persisted (lost on restart) |
| `DatasetSampleDocument` | Sample has been added to a dataset | MongoEngine ORM, written to MongoDB and persisted across sessions |

When a dataset is created, its `_sample_doc_cls` is a dynamically created subclass of `DatasetSampleDocument` named after the dataset's MongoDB collection. When a sample is created, its `_doc` is set to `NoDatasetSampleDocument` by default. Once it is added to the dataset, the `_doc` is swapped automatically to match the `_sample_doc_cls` of the dataset:
```python
    dataset = fo.Dataset(name="my_dataset")
    dataset._sample_doc_cls  # my_dataset(DatasetSampleDocument)

    sample = fo.Sample(filepath=...)
    sample._doc  # NoDatasetSampleDocument (in RAM only)

    dataset.add_sample(sample)
    sample._doc  # my_dataset(DatasetSampleDocument) (persisted to MongoDB)
```

The swap inside `add_sample` works as follows ([fiftyone/fiftyone/core/dataset.py#L3978](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/dataset.py#L3978)):
1. The sample is serialized to a plain dict and written to MongoDB via `insert_many`, MongoDB assigns it a real `_id`
2. A new `DatasetSampleDocument` is constructed from that dict (`_sample_dict_to_doc`)
3. `sample._set_backing_doc(doc, dataset=self)` replaces `sample._doc` with the new object

`add_sample` and `add_samples` share the same core logic but differ in scale:
| | `add_sample` | `add_samples` |
|---|---|---|
| Input | single `Sample` | iterable of `Sample`s |
| Batching | one `insert_many` call directly | splits into chunks via `Batcher`, one `insert_many` per batch |
| Progress bar | no | yes (`progress` param) |
| Generator mode | no | opt-in via `generator=True` (default `False` returns a flat list of all IDs once all batches are written; `True` yields each batch's IDs as they are inserted, allowing the caller to pipeline work without waiting for the full insert to complete) |

`add_sample` is a thin convenience wrapper around `_add_samples_batch([sample])`. `add_samples` uses batching to avoid sending one massive request to MongoDB and keeps memory usage bounded.

### Detections
`fo.Detections` is defined at [fiftyone/fiftyone/core/labels.py#L647](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/labels.py#L647). It is a container for a list of `Detection` objects for a single image. It has two conversion methods:
- `to_polylines()`: converts each detection's bounding box (or instance mask boundary if present) into a `Polylines` representation
- `to_segmentation()`: renders detections that have instance masks into a pixel mask (`Segmentation`), skipping any detections without masks
```python
    fo.Detections(detections=detections) # creating a Detections object, where detections is a list of fo.Detection objects
```

### Detection
`fo.Detection` is defined at [fiftyone/fiftyone/core/labels.py#L438](https://github.com/cxl-garage/fiftyone/blob/develop/fiftyone/core/labels.py#L438). It represents a single object detection and supports both 2D and 3D objects:
- 2D: requires `bounding_box` as `[top-left-x, top-left-y, width, height]` in relative `[0, 1]` coordinates. Optionally accepts `mask` (numpy array) or `mask_path` (local path to PNG) for instance segmentation.
- 3D: requires `location`, `dimensions`, and `rotation` in scene coordinates instead of a bounding box.

Other key fields: `label` (class string), `confidence` (float in `[0, 1]`, used for downstream filtering in fiftyone), `index` (object index). Any additional kwargs are stored as dynamic fields.
```python
    # example of adding a Detection object to a list
    detections = []
    ...
    x1, y1, x2, y2 = xmins[i], ymins[i], xmaxs[i], ymaxs[i]
    det_kwargs = {key: bbox_cols[key][i] for key in bbox_metadata_keys} # extract metadata for this annotation
    det_kwargs["bounding_box"] = [x1, y1, x2 - x1, y2 - y1]
    det_kwargs["label"] = det_kwargs.pop("common_name") # set box labels to common name
    det_kwargs["confidence"] = det_kwargs.pop("bb_confidence") # confidence is a built-in field that allows for downstream filtering in fiftyone
    detections.append(fo.Detection(**det_kwargs))
```