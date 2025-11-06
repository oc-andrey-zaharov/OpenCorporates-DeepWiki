// Mermaid diagram examples for wiki generation prompts
// CRITICAL: These examples demonstrate proper syntax and formatting to help the LLM generate valid diagrams

export const MERMAID_EXAMPLE_1 = `flowchart TD
    subgraph datasources["Data Sources"]
        lambda["AWS Lambda"]
        spark["Spark Jobs"]
        python["Python Apps"]
    end
    
    subgraph processing["Processing"]
        client["OC Lineage<br/>Client"]
        manifest["Manifest<br/>Generator"]
    end
    
    subgraph storage["Storage"]
        console["Console"]
        file["Local File"]
        s3["AWS S3"]
    end
    
    lambda --> client
    spark --> client
    python --> client
    
    client --> console
    client --> file
    client --> s3
    manifest -.-> s3`;

export const MERMAID_EXAMPLE_2 = `sequenceDiagram
    autonumber
    participant pipeline as Pipeline
    participant client as OC Client
    participant transport as Transport
    participant storage as Storage
    
    pipeline->>client: Job START/COMPLETE
    client->>transport: Emit events
    
    alt S3 Transport
        transport->>storage: Write to S3
    else File Transport
        transport->>client: Write to file
    end
    
    Note over storage: Partitioned by date`;

export const MERMAID_EXAMPLE_3 = `flowchart TD
    A{"Need I/O<br/>Provenance?"}
    
    A -->|Yes| B["Generate<br/>Manifest"]
    A -->|No| C{"Need<br/>Metadata?"}
    
    C -->|No| D["Complete"]
    C -->|Yes| E{"Small &<br/>Structured?"}
    
    E -->|Yes| F["Embed<br/>Metadata"]
    E -->|No| G["Sidecar<br/>Metadata"]
    
    B --> D
    F --> D
    G --> D`;

// Additional validation rules enforced in these examples:
// 1. Node IDs are simple alphanumeric (e.g., A, B, C, not complex labels)
// 2. Node labels use quotes and are concise (max 3-4 words per line)
// 3. Line breaks in labels use <br/> consistently
// 4. Subgraphs in flowcharts use simple descriptive names
// 5. Sequence diagrams have all participants declared upfront
// 6. Arrow syntax is simple (->, ->>), avoiding complex patterns
// 7. No special characters or escaping within labels
// 8. All diagram directives (flowchart TD, sequenceDiagram) are on separate lines
