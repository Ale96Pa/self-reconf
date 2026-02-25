#image Java with Maven
FROM maven:3.9.6-eclipse-temurin-17 AS builder

#copy the project and compile
WORKDIR /app
COPY . .
RUN mvn -pl example -am clean package -DskipTests


FROM eclipse-temurin:17-jdk

WORKDIR /app

#copy the compiled jar 
COPY --from=builder /app/example/target/pbft-java-example-1.0-SNAPSHOT.jar app.jar

#start with replica launcher
ENTRYPOINT ["java", "-cp", "app.jar", "com.gmail.woodyc40.pbft.ReplicaLauncher"]
