# Use AWS Lambda Python 3.8 image as base
FROM public.ecr.aws/lambda/python:3.8

# Setting the compatible versions of libraries
ARG HADOOP_VERSION=3.2.4
ARG AWS_SDK_VERSION=1.11.901
ARG PYSPARK_VERSION=3.3.0
ARG HUDI_FRAMEWORK_VERSION=0.12.2
ARG SERVICE_NAME

# Perform system updates and install dependencies
RUN yum update -y && \
    yum -y update zlib && \
    yum -y install wget && \
    yum -y install yum-plugin-versionlock && \
    yum -y versionlock add java-1.8.0-openjdk-1.8.0.362.b08-0.amzn2.0.1.x86_64 && \
    yum -y install java-1.8.0-openjdk && \
    yum -y install unzip && \
    pip install --upgrade pip && \
    pip install pyspark==$PYSPARK_VERSION boto3 && \
    yum clean all

# Set environment variables for PySpark
ENV SPARK_HOME="/var/lang/lib/python3.8/site-packages/pyspark"
ENV SPARK_VERSION=3.3.0
ENV PATH=$PATH:$SPARK_HOME/bin
ENV PATH=$PATH:$SPARK_HOME/sbin
ENV PATH=$SPARK_HOME/python:$PATH
ENV PATH=${PATH}:${JAVA_HOME}/bin
ENV PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-0.10.9-src.zip:$PYTHONPATH

RUN mkdir $SPARK_HOME/conf && \
    echo "SPARK_LOCAL_IP=127.0.0.1" > $SPARK_HOME/conf/spark-env.sh && \
    echo "JAVA_HOME=/usr/lib/jvm/$(ls /usr/lib/jvm |grep java)/jre" >> $SPARK_HOME/conf/spark-env.sh

# download jars
RUN wget -q https://repo1.maven.org/maven2/org/apache/hudi/hudi-spark3.3-bundle_2.12/${HUDI_FRAMEWORK_VERSION}/hudi-spark3.3-bundle_2.12-${HUDI_FRAMEWORK_VERSION}.jar -P ${SPARK_HOME}/jars/ && \ 
    wget -q https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar -P ${SPARK_HOME}/jars/ && \
    wget -q https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar -P ${SPARK_HOME}/jars/

# Add spark-class file for memory settings (1GB)
ADD src/docker/spark-class $SPARK_HOME/bin/
RUN chmod -R 755 $SPARK_HOME

# Add service code with proper package structure
ADD src/docker/${SERVICE_NAME} ${LAMBDA_TASK_ROOT}/
RUN ls ${LAMBDA_TASK_ROOT}/ && pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

CMD [ "main.lambda_handler" ]