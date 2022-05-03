# Comment to GitHub

> Convert blog comments to GitHub PRs

A small docker container that takes comments from a blog, offers a check
with reCaptcha and posts them as PR on a GitHub project.


## Usage

### Run with Docker

With the configuration stored in a file `.env`, the daemon can be started as follows: 

```bash
docker run --rm \
  -p 8080:8080 \
  --env-file .env \
  mrtux/comment2gh
```

### Configuration

Configuration is done using environment variables:

* `MANAGEMENT_PORT`: Port for the HTTP Management Service (default: 8080)


## API

### Health endpoint

The daemon features a health endpoint to check if all components are up and running.
While a certain amount of resilience is built into the handlers, an overall check routine using the Docker
health checks has been established. 
The endpoint works similar to health endpoints expected for Microservices, e.g. in a Kubernetes runtime environment:
* HTTP status 200 is returned when the service is considered healthy.
* HTTP status 500 is returned when the service is considered unhealthy.
* Additional information can be found in the return message. Please refer to the [OAS3](src/OAS3.yml) for details.

The [Dockerfile](Dockerfile) sets the container up for a health check every 10s, otherwise sticks to the Docker defaults.

To expose the health endpoint, route port 8080 to a port that is suitable for the deployment environment. 


## Maintainers

* [@penguineer](https://github.com/penguineer)


## Contributing

PRs are welcome!

If possible, please stick to the following guidelines:

* Keep PRs reasonably small and their scope limited to a feature or module within the code.
* If a large change is planned, it is best to open a feature request issue first, then link subsequent PRs to this
  issue, so that the PRs move the code towards the intended feature.


## License

MIT © 2022 Stefan Haun and contributors
