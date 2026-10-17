"""One execution request for COI analysis."""
import argparse
import json
from .conflict_agent import ConflictOfInterestAgent
from .graph_manager import close_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True)
    parser.add_argument("--counterparty", required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--entity", action="append", default=[])
    parser.add_argument("--pdf", help="Optional PDF to ingest before analysis")
    args = parser.parse_args()
    try:
        if args.pdf:
            from .ldi.pipeline import analyze_pdf
            result = analyze_pdf(args.pdf, doc_id=args.doc_id, client_entity=args.client,
                                 counterparty_entity=args.counterparty, additional_entities=args.entity)
        else:
            result = ConflictOfInterestAgent().run(doc_id=args.doc_id, client_entity=args.client,
                counterparty_entity=args.counterparty, additional_entities=args.entity).to_dict()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "complete" else 2
    finally:
        close_graph()


if __name__ == "__main__":
    raise SystemExit(main())
