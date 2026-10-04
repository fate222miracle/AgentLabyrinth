/** Identify the page owner of asynchronous results without cancelling server work. */
export class RequestGeneration {
  private generation = 0;

  begin(): number {
    return ++this.generation;
  }

  capture(): number {
    return this.generation;
  }

  isCurrent(request: number): boolean {
    return request === this.generation;
  }
}
