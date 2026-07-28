# Explainability Data Flow

```text
validated artifact -> public projection -> identity/version/checksum extraction
 -> direct rule/action/provenance/validation/compilation fact mapping
 -> dependency chain and decision trace -> canonical checksum validation
 -> atomic explanation storage -> search/trace/export/viewer
```

The input is converted to a separate plain read-only projection. No method on an upstream artifact or Engine is invoked by the ENG-016 package, and generation never writes through an upstream provider.
