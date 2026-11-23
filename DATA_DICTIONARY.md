# Data dictionary

This dictionary records only meanings established by SQL comments, field names, the CSV mapping in [ingest_call_event.py](./ingest_call_event.py#L6), or observed values. A name such as `x`, `lon`, or `s` is not treated as a verified unit definition. Ambiguous fields are explicitly flagged.

## Reference tables

| Table.field | Meaning | Units / valid values | Source / confidence |
|---|---|---|---|
| `bat.bat_id` | Database bat identifier | Integer primary key | SQLite schema; confirmed |
| `bat.bat_code` | Bat code, examples include `batC` | Non-null, unique text | SQL comment and CSV `bat`; confirmed |
| `bat.species` | Species | Not established | Schema only; ambiguous |
| `bat.sex` | Sex code | `M`, `F`, `U`; default `U` | CHECK constraint; confirmed code semantics not documented |
| `bat.notes` | Free-form bat notes | Text | Schema only |
| `session.session_id` | Database session identifier | Integer primary key | Schema; confirmed |
| `session.session_date` | Session date | Text, intended `YYYY-MM-DD`; globally unique | SQL comment and importer conversion; confirmed format intent |
| `session.notes` | Session notes | Text | Schema only |
| `condition.condition_id` | Database condition identifier | Integer primary key | Schema |
| `condition.cond_code` | Canonical condition code | Current values `D`, `EM`, `EM-R1`, `G`, `L`, `R1`, `R2`; unique | Schema and current data; scientific meanings not established |
| `condition.cond_code_raw` | Raw pre-canonical condition code | Text | Schema/importer design; empty in current DB |
| `condition.theta_code` | Optional theta code | Examples in schema comment: `0P`, `-23P`, `0D`, `0E` | SQL comment; semantics not established |
| `condition.display_name` | Human-readable condition name | Text | Schema; empty in current DB |
| `condition.plot_color`, `plot_palette` | Plotting metadata | Text | Schema; not used by inspected viewers |
| `condition.notes` | Condition notes | Text | Schema |
| `trial.trial_id` | Database trial identifier | Integer primary key | Schema |
| `trial.session_id`, `bat_id`, `condition_id` | Trial parent references | Required foreign keys | Schema; confirmed |
| `trial.trial_num` | Trial number from source/Vicon filename convention | Required integer | SQL comment; exact source semantics not independently verified |
| `trial.vicon_trial_num` | Optional Vicon trial number | Integer | Schema comment; optional |
| `trial.mic_trial_num` | Optional microphone trial number | Integer | Schema comment; optional |
| `trial.train_or_test` | Training/testing label | Current value `Testing`; no database CHECK | Schema comment/current data; exact vocabulary not enforced |
| `trial.landmark` | Optional landmark label | Example `landmark01` | Schema comment; semantics not established |
| `trial.source_file_path` | Source file location | Text | Schema; empty in current DB; path policy not defined |
| `trial.processing_run_id` | Processing-run reference | Nullable FK | Schema; null in current DB |
| `processing_run.processing_run_id` | Processing-run identifier | Integer primary key | Schema |
| `processing_run.name`, `description` | Processing recipe metadata | Text | Schema; table empty |
| `processing_run.created_at` | Run creation timestamp | SQLite `datetime('now')` text default; timezone policy not documented | Schema; table empty |
| `binning_scheme.binning_scheme_id` | Binning scheme identifier | Integer primary key | Schema |
| `binning_scheme.name` | Binning scheme name | Required, unique text | Schema; table empty |
| `binning_scheme.variable` | Variable being binned | Required text | Schema comment gives `first_trip_s` example; table empty |
| `binning_scheme.method` | Binning method | Required; comments suggest `cut` or `qcut`, not enforced | Schema; table empty |
| `binning_scheme.params_json` | Binning parameters | Intended JSON string; not JSON-validated | Schema comment |
| `binning_scheme.notes` | Binning notes | Text | Schema |

## `call_event` fields

| Field | Meaning | Units / valid values | Source / confidence |
|---|---|---|---|
| `call_id` | Call-event database identifier | Integer primary key | Schema |
| `trial_id` | Parent trial | Required FK | Schema |
| `call_num` | Sequential call index within trial | Integer; unique per trial when non-null | Importer assigns sorted row index starting at 1; confirmed implementation |
| `time_s` | Call time | Seconds by field name; required | CSV `time` mapping and schema; unit strongly indicated, not independently defined |
| `good_call` | Call-quality flag | Intended 0/1; nullable; CHECK | CSV mapping and schema; importer does not explicitly normalize all encodings |
| `behind` | Behind/front flag | Intended 0/1; nullable; CHECK | CSV mapping and schema; exact spatial convention not documented |
| `x_call`, `y_call`, `z_call` | Position at call time | Coordinate units not specified | CSV mapping, SQL comment, viewers; ambiguous units/reference frame |
| `x`, `y`, `z` | Trajectory context position | Coordinate units not specified | CSV mapping and SQL comment; ambiguous |
| `s` | Trajectory/path scalar | Not established | CSV mapping; ambiguous |
| `first_trip_s` | First-trip position/time scalar | Name suggests seconds, but definition not supplied | CSV mapping and field name; ambiguous |
| `trip` | Trip identifier/index | Integer; current data includes negative values | CSV mapping/current data; vocabulary not constrained |
| `lon` | Longitude-like measurement | Unit/reference frame not specified | CSV mapping; ambiguous |
| `long_angle_to_target` | Longitudinal angle to target | Angle unit not specified | CSV mapping; ambiguous |
| `lon_angle_to_target` | Longitudinal angle to target | Angle unit not specified | CSV mapping; ambiguous; similar name requires clarification |
| `lon_angle_to_target_medfiltered` | Median-filtered longitudinal target angle | Angle unit not specified | CSV mapping; ambiguous |
| `norm_hd_x/y/z` | Normalized head-direction vector | Dimensionless vector components; frame not specified | SQL comment and CSV mapping; frame ambiguous |
| `norm_hd_2d_x/y` | 2-D normalized head-direction vector | Dimensionless; frame not specified | SQL comment and CSV mapping |
| `norm_beam_aim_vec_x/y/z` | Normalized beam aiming vector | Dimensionless; frame not specified | SQL comment and CSV mapping |
| `norm_beam_aim_vec_2d_x/y` | 2-D normalized beam aiming vector | Dimensionless; frame not specified | SQL comment and CSV mapping |
| `lon_beam`, `lat_beam` | Beam longitude/latitude-like angles | Units not specified | SQL comment says world coordinates; ambiguous |
| `lon_head`, `lat_head` | Head longitude/latitude-like angles | Units not specified | SQL comment says world coordinates; ambiguous |
| `lon_aim_to_head`, `lat_aim_to_head` | Aim relative to head angles | Units not specified | SQL comment says head coordinates; ambiguous |
| `inter_click_interval` | Interval between clicks | Likely seconds by name; pipeline convention not defined | SQL comment and field name; unit needs confirmation |
| `inter_click_distance_3D`, `inter_click_distance_2D` | 3-D/2-D distance between clicks | Distance units not specified | SQL comment; ambiguous |
| `hd_sd_rad` | HD-SD value in radians | Radians by source name | CSV mapping `HD-SD_rad`; confirmed label, formula unknown |
| `hd_sd_deg` | HD-SD value in degrees | Degrees by source name | CSV mapping `HD-SD`; formula unknown |
| `hd_sd_medianfiltered_rad`, `hd_sd_medianfiltered_deg` | Median-filtered HD-SD | Radians/degrees by field names | CSV mapping; formula unknown |
| `binned_s`, `binned_s_all` | Binned `s` values | Likely same base unit as `s`; not defined | SQL comment says binning fields; scheme table empty |
| `inter_click_interval_bcfiltered` | BC-filtered click interval | Likely seconds; filter definition not present | CSV mapping/field name; ambiguous |
| `inter_click_distance_3D_bcfiltered`, `2D_bcfiltered` | BC-filtered click distances | Units not specified | CSV mapping; filter definition absent |
| `lon_aim_to_head_bcfiltered`, `lat_aim_to_head_bcfiltered` | BC-filtered relative aim angles | Units not specified | CSV mapping; filter definition absent |
| `lon_beam_bcfiltered`, `lat_beam_bcfiltered` | BC-filtered beam angles | Units not specified | CSV mapping; filter definition absent |
| `lon_head_bcfiltered`, `lat_head_bcfiltered` | BC-filtered head angles | Units not specified | CSV mapping; filter definition absent |
| `hd_sd_bcfiltered` | BC-filtered HD-SD | Unit not specified | CSV mapping; filter definition absent |
| `pair_id` | Pair identifier on call event | Integer; sentinel `-1` is used by GUI filters; no FK | CSV mapping/current code; exact pairing rule not documented |
| `pair_click_angle_lon`, `pair_click_angle_lat` | Pair angle metrics | Units not specified | CSV mapping; ambiguous |
| `pair_id_binned`, `pair_id_binned_all` | Binned pair identifiers/values | Stored as REAL; meaning not defined | CSV mapping and schema; ambiguous type/semantics |
| `pair_click_angle_lon_bcfiltered`, `pair_click_angle_lat_bcfiltered` | Filtered pair angle metrics | Units not specified | CSV mapping; filter definition absent |

## Missing-value and provenance notes

Most `call_event` measurements are nullable. The repository does not define whether null means unavailable, filtered, not applicable, or failed measurement. The current CSV has missing `time` and call-coordinate values, while `time_s` is required in SQLite. The importer does not record a row-level rejection/quarantine report. The checked-in trials have null `source_file_path` and `processing_run_id`, so field meaning alone is not enough to reproduce their derivation.
